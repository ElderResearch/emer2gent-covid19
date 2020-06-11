
suppressPackageStartupMessages({
  library(tidyverse)
  library(glue)
  library(assertthat)
})


# Miscellany --------------------------------------------------------------

#' Group a table by county FIPS code
group_abt <- function(tbl) {
  tbl %>% group_by(county_fip)
}

#' Group a table _and_ arrange it by county_fip and date
group_arrange_abt <- function(tbl) {
  tbl %>% group_abt() %>% arrange(county_fip, date)
}


# ABT prep ----------------------------------------------------------------

#' Create a clean ABT from raw sources
fetch_abt <- function(src) {
  message("Reading CSV")
  abt <- suppressMessages(read_csv(src, guess_max = 3.5e5))
  assert_that(nrow(abt) == 424170)

  # Fix the cumulative counts
  abt <- abt %>%
    group_arrange_abt() %>%
    mutate(
      old_ = confirmed,
      confirmed = correct_negative_infections(old_)
    ) %>%
    ungroup() %>%
    select(-old_)

  # Add count checks?

  # Key columns
  abt <- abt %>%
    select(
      state_code, county_fip, date,
      acs_pop_total, confirmed,
      phase_1, phase_2,
      acs_median_hh_inc_total,
      acs_race_white,
      starts_with("acs_age_"),
      tmpf_mean, relh_mean,
      retail_and_recreation, grocery_and_pharmacy, parks,
      transit_stations, workplaces, residential
    )

  # Recode Phase 1 as 2 indicators: ever and current
  message("Recoding Phase 1")
  abt <- abt %>%
    group_arrange_abt() %>%
    mutate(
      phase_1_active = as.integer(phase_1 == 1),
      phase_1_ever = suppressWarnings(as.integer(
        any(phase_1_active) &
        date >= min(date[phase_1_active == 1]))
      )) %>%
    ungroup() %>%
    select(-phase_1)

  message("Recoding Phase 2")
  abt <- abt %>%
    group_arrange_abt() %>%
    mutate(
      phase_2_active = as.integer(phase_2 == 1),
      phase_2_ever = suppressWarnings(as.integer(
        any(phase_2_active) &
        date >= min(date[phase_2_active == 1]))
      )) %>%
    ungroup() %>%
    select(-phase_2)

  # Missing median incomes are replaced with pop-weighted medians
  message("Imputing median incomes")
  abt <- abt %>%
    group_by(state_code) %>%
    group_modify(~ {
      if (!any(is.na(.x$acs_median_hh_inc_total))) return(.x)

      lookup <- distinct(.x, county_fip, acs_pop_total, acs_median_hh_inc_total)
      idx <- is.na(.x$acs_median_hh_inc_total)

      .x$acs_median_hh_inc_total[idx] <-
        median(rep(
          lookup[["acs_median_hh_inc_total"]],
          lookup[["acs_pop_total"]]),
          na.rm = T
        )

      return(.x)
    }) %>%
    ungroup()

  assert_that(nrow(abt) == 424170)
  assert_that(sum(is.na(abt$acs_median_hh_inc_total)) == 0)

  # Compute a simple minority representation metric
  abt <- abt %>%
    mutate(acs_race_f_minority = 1 - acs_race_white / acs_pop_total)

  # Bin ages according to how CDC does it
  # https://www.cdc.gov/nchs/nvss/vsrr/covid_weekly/index.htm#AgeAndSex
  abt <- abt %>%
    mutate(
      acs_f_age_le_24 = (
        acs_age_lt_05 + acs_age_05_09 + acs_age_10_14 + acs_age_15_17 +
        acs_age_18_19 + acs_age_20 + acs_age_21 + acs_age_22_24
      ),
      acs_f_age_25_34 = acs_age_25_29 + acs_age_30_34,
      acs_f_age_35_44 = acs_age_35_39 + acs_age_40_44,
      acs_f_age_45_54 = acs_age_45_49 + acs_age_50_54,
      acs_f_age_55_64 = acs_age_55_59 + acs_age_60_61 + acs_age_62_64,
      acs_f_age_65_74 = acs_age_65_66 + acs_age_67_69 + acs_age_70_74,
      acs_f_age_75_84 = acs_age_75_79 + acs_age_80_84,
      acs_f_age_85_ge = acs_age_85_up
    ) %>%
    mutate(across(starts_with("acs_f_age"), ~ . / acs_pop_total)) %>%
    select(-starts_with("acs_age"))

  # Fill weather NAs by county, then by state
  message("Imputing weather")
  abt <- abt %>%
    group_arrange_abt() %>%
    fill(tmpf_mean, .direction = "updown") %>%
    fill(relh_mean, .direction = "updown") %>%
    group_by(state_code) %>%
    group_modify(~ {
      if (!any(is.na(.x$tmpf_mean)) & !any(is.na(.x$relh_mean)))
        return(.x)

      # Use statewide mean values per month
      mean_vals <- .x %>%
        mutate(month = lubridate::month(date)) %>%
        group_by(month) %>%
        summarize(
          new_t_ = mean(tmpf_mean, na.rm = T),
          new_h_ = mean(relh_mean, na.rm = T),
          .groups = "drop"
        )

      .x %>%
        mutate(month = lubridate::month(date)) %>%
        left_join(mean_vals, by = "month") %>%
        mutate(
          tmpf_mean = if_else(is.na(tmpf_mean), new_t_, tmpf_mean),
          relh_mean = if_else(is.na(relh_mean), new_h_, relh_mean)
        ) %>%
        select(-new_h_, -new_t_, -month)
    }) %>%
    ungroup()

  assert_that(nrow(abt) == 424170)
  assert_that(sum(is.na(abt$tmpf_mean)) == 0)
  assert_that(sum(is.na(abt$relh_mean)) == 0)

  # Impute missing mobility data
  message("Imputing mobility")
  abt <- abt %>%
    group_by(state_code) %>%
    group_modify((~ {
      .cols <- c(
        "retail_and_recreation",
        "grocery_and_pharmacy",
        "parks" ,
        "transit_stations",
        "workplaces",
        "residential"
      )
      for (col in .cols) {
        if (!any(is.na(.x[[col]]))) next
        .x[[col]] <- replace_na(.x[[col]], 0)
      }
      .x
    })) %>%
    ungroup()

  assert_that(sum(is.na(abt)) == 0)

  return(final_transform(abt))
}

#' Correct/smooth cumulative infections
#'
#' Back-correct the confirmed infection counts to make changes non-negative.
#' This function takes a vector, computes the difference between entries,
#' and fixed negative values.
correct_negative_infections <- function(col) {
  new_col <- col

  # Iterate backwards to index 2 (leave 1 out for calculating difference)
  for (i in seq(length(new_col), 2, -1)) {
    it <- new_col[i] - new_col[i - 1]
    if (it >= 0) next
    # Make it go to zero by fixing the last record
    new_col[i - 1] <- new_col[i - 1] + it
  }

  new_col
}

#' Include only the most relevant columns for modeling
final_transform <- function(data) {
  data %>%
    group_arrange_abt() %>%
    transmute(
      state_code,
      date,
      # SIR
      pop = acs_pop_total,
      cuml_inf = confirmed,
      suscept_norm = 1 - cuml_inf / pop,
      daily_inf = confirmed - lag(confirmed),
      daily_inf_target = lead(daily_inf),
      # Policies
      phase_1_active,
      phase_1_ever,
      phase_2_active,
      phase_2_ever,
      # Weather
      tmpf_mean,
      relh_mean,
      # Demography
      median_inc = acs_median_hh_inc_total,
      minority_frac = acs_race_f_minority,
      age_le_24_frac = acs_f_age_le_24,
      age_25_34_frac = acs_f_age_25_34,
      age_35_44_frac = acs_f_age_35_44,
      age_45_54_frac = acs_f_age_45_54,
      age_55_64_frac = acs_f_age_55_64,
      age_65_74_frac = acs_f_age_65_74,
      age_75_84_frac = acs_f_age_75_84,
      age_85_ge_frac = acs_f_age_85_ge,
      # Behavior
      mobility_retail_and_recreation = retail_and_recreation,
      mobility_grocery_and_pharmacy = grocery_and_pharmacy,
      mobility_parks = parks,
      mobility_transit_stations = transit_stations,
      mobility_workplaces = workplaces,
      mobility_residential = residential
    ) %>%
    na.omit() %>%
    ungroup()
}


# Linear models -----------------------------------------------------------

# Extract lm fits from a single-row table using broom
extract_lm <- function(tbl, model_col, which = c("summary", "coefs")) {
  which <- match.arg(which, several.ok = T)
  assert_that(nrow(tbl) == 1)

  # Get model summary and convert to "term/estimate" format
  ms_ <- tibble()
  if ("summary" %in% which) {
    ms_ <- tbl %>%
      pull({{model_col}}) %>%
      extract2(1) %>%
      broom::glance() %>%
      pivot_longer(everything(), names_to = "term", values_to = "estimate") %>%
      mutate(.component = "summary") %>%
      relocate(.component, 0)
  }

  # Get coefs
  coef_ <- tibble()
  if ("coefs" %in% which) {
    coef_ <- tbl %>%
      pull({{model_col}}) %>%
      extract2(1) %>%
      broom::tidy(conf.int = 0.89) %>%
      mutate(.component = "coefs") %>%
      relocate(.component, 0)
  }

  bind_rows(ms_, coef_)
}



# Apply models over time --------------------------------------------------

roll_in_time <- function() {

}
