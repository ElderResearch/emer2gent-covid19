# get_weather_data.R
#
# This script (when run from the command line) will download various weather
# related measurements for the nearest* ASOS weather station to every
# county in the USA. We assume that you have a valid Google Maps API in order
# to geocode counties to allow us to match counties to ASOS stations. See the
# project README for more details.
#
# Usage (from the RStudio Project root dir):
#   `Rscript R/get_weather_data.R --start-date 2020-01-01 --end-date 2020-07-01`
#
# Returns:
#  Artifacts dropped in the `data` directory. Including
#  `weather_by_country_fips.gz`

suppressPackageStartupMessages({
  library(argparser)
  library(dplyr)
  library(furrr)
  library(futile.logger)
  library(future)
  library(geosphere)
  library(ggmap)
  library(glue)
  library(purrr)
  library(readr)
  library(riem)
  library(rvest)
  library(stringr)
  library(tibble)
})

# County-FIPS -------------------------------------------------------------

#' Download State and County FIPS Codes
#' 
#' This function will scrape US State and County FIPS from two separate
#' Wikipedia pages and combine them into one data.frame. Note: US territories
#' (e.g., Puerto Rico, Guam) will be included in the output data set.
#'
#' @return a tibble
get_fip_codes <- function() {
  
  urls <- list(
    'county'='https://en.wikipedia.org/wiki/List_of_United_States_FIPS_codes_by_county',
    'state'='https://en.wikipedia.org/wiki/Federal_Information_Processing_Standard_state_code'
  )
  
  flog.info('Pulling FIPS from:\n\t%s', glue_collapse(urls, sep = '\n\t'))
  
  tbls <- map(urls, function(u) read_html(u) %>% html_table(fill=TRUE))
  is_fips <- map(tbls, function(tbl) {
    map_lgl(tbl, ~ any(c('fips', 'alpha code') %in% tolower(names(.x))))
  })
  
  fips <- map2(tbls, is_fips, ~ .x[[which(.y)]]) %>%
    map(function(df) {
      as_tibble(df) %>%
        mutate(across(where(is.character), ~ str_remove_all(.x, '[[:punct:]]'))) %>% 
        mutate(across(where(is.character), ~ gsub('Hawaiʻi','Hawaii', .x))) %>%
        mutate(across(where(is.character), str_trim)) %>%
        mutate(across(where(is.character), ~ na_if(.x, ''))) %>%
        na.omit()
    })
  
  colnames <- list(
    c('county_fip', 'county', 'state'),
    c('state', 'state_code', 'state_fip', 'status')
  )
  fips <- map2(fips, colnames, ~ set_names(.x, .y))
  fips <- reduce(fips, left_join, by='state') %>% 
    select(state, state_code, state_fip, county, county_fip)
  fips
}

#' GeoCode FIPS
#' 
#' A convenience function to enrich FIPS data with lon/lat, type, and other
#' categorical information provided by Google's Map API.
#'
#' @param google_api_key: (string) a valid google API key. See details for 
#'   additional information.
#'   
#' @details  See: https://cran.r-project.org/web/packages/ggmap/readme/README.html'
#'   for instructions on how to get a valid api key to use the geo-tagging
#'   service
#'
#' @return a tibble of gecoded county level fips
geocode_fips <- function(google_api_key=NULL) {
  
  if (file.exists('data/fips_geocoded.csv')) {
    flog.info('Found a copy of `fips_geocoded.csv`. Returning this file.')
    f <- suppressMessages(read_csv('data/fips_geocoded.csv'))
    return(f)
  }
  
  if (is.null(google_api_key) | nchar(google_api_key) < 1) {
    stop_msg <- glue("
    `google_api_key` was not provided. \\
    See: https://cran.r-project.org/web/packages/ggmap/readme/README.html') \\
    for instructions on how to obtain a valid Google api key
  ")
    flog.fatal(stop_msg); stop(stop_msg)
  }
  
  fips <- get_fip_codes()
  flog.info("Geocoding Fips ... ")
  register_google(key=google_api_key)
  search_terms <- paste(fips$county, fips$state, sep=', ')
  flog.info('Geocoding %s counties', length(search_terms))
  coords <- map2_dfr(search_terms, seq_along(search_terms), function(term, i) {
    flog.info('Geocoding %s of %s', i, length(search_terms))
    suppressMessages(geocode(term, output='more', override_limit=TRUE))
  })
  fips <- bind_cols(fips, coords)
  flog.info("FIPS geocoded sucesfully")
  write.csv(fips, 'data/fips_geocoded.csv', row.names=FALSE)
}

# Main-Routine ------------------------------------------------------------

if (!interactive()) {
  
  # Arg-Parsing -------------------------------------------------------------
  parser <- arg_parser('Download ASOS Weather Data for all 50 US States')
  parser <- add_argument(parser, '--start-date', help='Starting Date "YYYY-MM-DD" format', default='2020-01-01')
  parser <- add_argument(parser, '--end-date', help='Starting Date "YYYY-MM-DD" format', default='2020-07-01')
  args <- parse_args(parser)
  
  flog.info('.libpaths: %s', .libPaths())
  flog.info('.R version: %s', R.version.string)
  flog.info('start date: %s, end_date: %s', args$start_date, args$end_date)
  
  api_key <- Sys.getenv('GOOGLE_MAP_API_KEY')
  fips <- geocode_fips(google_api_key = api_key)
  
  # ASOS-Stations ------------------------------------------------------------
  
  # riem package provides the functionality to download asos data
  flog.info('Pulling all US county ASOS Stations')
  all_networks <- riem_networks()
  
  us_network <- all_networks %>%
    filter(grepl(paste0(datasets::state.name, collapse='|'), name)) %>%
    filter(grepl('ASOS', code))
  
  stations <- group_split(us_network, code) %>% 
    map(function(df) riem_stations(df$code)) %>%
    set_names(us_network$code) %>%
    bind_rows(.id='network_code')
  
  # Subset stations to those that are closest to each county using Haversine dist
  # distance in meters; (lon, lat) pairs
  hdist <- distm(fips[c('lon', 'lat')], stations[c('lon', 'lat')], fun=distHaversine)
  
  # Calculate the top N closest locations + distance for each county
  N <- 3
  top_n_indx <- t(apply(hdist, 1, order)[1:N,])
  top_n_dist <- t(apply(hdist, 1, function(x) sort(x)[1:N]))/1e3
  top_n_stations <- filter(stations, row_number() %in% unique(c(top_n_indx)))
  
  # Download-Data -----------------------------------------------------------
  
  #start_dt <- '2020-01-01'; end_dt <- '2020-07-01'
  start_dt <- args$start_date; end_dt <- args$end_date
  flog.info("Pulling ASOS Data from %s to %s", start_dt, end_dt)
  
  # Set a "plan" for how the code should run. The easiest is `multiprocess`
  # On Mac this picks plan(multicore) and on Windows this picks plan(multisession)
  plan(multiprocess)
  
  # Statistics to generate for each dataset
  stats <- list(
    min  = ~min(.x, na.rm=TRUE),
    mean = ~mean(.x, na.rm=TRUE),
    max  = ~max(.x, na.rm=TRUE)
  )
  
  # Only include the closest station(s) to each county; break into chunks to use
  # parallel map
  stations_ <- pull(top_n_stations, id) %>% unique()
  stations_ <- split(stations_, ceiling(seq_along(stations_)/100))
  
  # Extract Measures for closest stations
  measures <- map2(stations_, seq_along(stations_), function(chunk, i) {
    flog.info('Downloading Weather for Station Chunk %s of %s', i, length(stations_))
    future_map(chunk, function(station) {
      df <- riem_measures(station=station, start_dt, end_dt)
      agg <- df %>% 
        mutate(station=as.character(station)) %>%
        mutate(date = as.Date(valid)) %>%
        group_by(station, date, lon, lat) %>% 
        summarise(
          across(where(is.numeric), stats, .names='{col}_{fn}'),
          n=n(),
          .groups='drop'
        )
      rm(df); gc()
      return(agg)
    })
  })
  flog.info('Completed ASOS Data Pull')
  # Create one massive data.frame
  measures_df <- map(measures, bind_rows) %>% bind_rows() %>%
    mutate(across(where(is.numeric), ~ ifelse(is.infinite(.x), NA, .x)))
  
  # Station-Selection -------------------------------------------------------
  
  # Determine which station to select by minimizing the following:
  #  1. missingness in measurements (temp, humidity, dew point)
  #  2. missingness in dates of data collection
  flog.info('Determining the nearest ASOS station to each county ...')
  # Station Report
  station_nan_report <- group_by(measures_df, station) %>% 
    summarise(
      min_date = min(date), 
      max_date = max(date),
      tmpf_na = mean(is.na(tmpf_mean)), 
      dwpf_na = mean(is.na(dwpf_mean)), 
      relh_na = mean(is.na(relh_mean)), 
      .groups = 'drop'
    )
  
  station_nan_report <- station_nan_report %>% 
    mutate(date_diff = difftime(max(max_date), max_date, units='days')) %>%
    mutate(missingness = (tmpf_na + dwpf_na + relh_na)/3)
  
  # Coerce ordering matrices into data.frames for mapping
  top_n_indx <- as_tibble(top_n_indx, .name_repair='minimal') %>% set_names(1:N)
  top_n_dist <- as_tibble(top_n_dist, .name_repair='minimal') %>% set_names(1:N)
  
  # Create long data.frame where unique county fips have the top N stations
  # ranked by distance
  fdist <- map(top_n_indx, ~ stations[.x, ] %>% rename_all(~ paste0('asos_', .x))) %>%
    map2_dfr(., top_n_dist, function(df, df_km) {
      rename(df, asos_network_id=asos_network_code, asos_station_id=asos_id) %>%
        rename(asos_station_name = asos_name) %>%
        mutate(dist_km = as.vector(df_km)) %>%
        mutate(dist_km = round(dist_km, 3)) %>%
        bind_cols(select(fips, -matches('km|^asos')), .)
    }, .id='dist_rank') %>%
    mutate(dist_rank = as.numeric(dist_rank))
  
  fdist <- arrange(fdist, county_fip, dist_rank) %>%
    left_join(station_nan_report, by=c('asos_station_id'='station')) %>%
    group_by(county_fip) %>% 
    arrange(missingness, date_diff) %>% 
    mutate(selected = row_number() == 1) %>%
    ungroup()
  
  flog.info('Optimal stations found.')
  fdist_all <- fdist
  fdist <- filter(fdist, selected) %>% select(-selected)
  
  # Final Data ----------------------------------------------------------------
  fips_df <- fips %>% 
    select(-matches('asos|dist_km')) %>%
    inner_join(select(fdist, county_fip, matches('dist|asos')), by='county_fip') %>%
    inner_join(select(measures_df, -matches('lat|lon')), by=c('asos_station_id'='station')) %>%
    select(-matches('^sky|^ice'))
  
  flog.info('Writing results.')
  # Write results
  write.csv(fdist_all, 'data/fips_to_asos_distance_comparison.csv', row.names=F)
  write.csv(fips_df, file=gzfile("data/weather_by_county_fips.csv.gz"), row.names=F)
}