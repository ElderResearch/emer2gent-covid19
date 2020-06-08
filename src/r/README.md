# `R` Weather Data

Access to all weather related data will be granted via the `riem` package.

This package collects weather data from ASOS stations (airports) via the
great website of the [Iowa Environment Mesonet](https://mesonet.agron.iastate.edu/request/download.phtml?network=IN__ASOS).

**Note**: A valid google maps API key is required in order to geocode state
and county FIPS. This is vital for matching ASOS sites to each and every county
in the USA. See [this link](https://cran.r-project.org/web/packages/ggmap/readme/README.html)
for info on how to obtain an API key.  

## `renv`
This project uses `renv` for package dependency management. Make sure you 
restore (`renv::restore()`) the project state before attempting to download
the weather data.  

## Usage

1. Make your API key available to the `R` process via an environment
   variable: `export GOOGLE_API_KEY=APIKEYCODE`  
2. Run the script from the RStudio project root directory (`src/r/trent`):
   `Rscript R/get_weather_data.R --start-date 2020-01-01 --end-date 2020-07-01`  
   
Artifacts are saved in the `data` directory (within the RStudio project
directory)  

The script runs in about an hour on a MBP. Your mileage may vary.  

## Measures

The following measures are collected from each ASOS weather station:

- **tmpf**: Air Temperature in Fahrenheit, typically @ 2 meters  
- **dwpf**: Dew Point Temperature in Fahrenheit, typically @ 2 meters  
- **relh**: Relative Humidity as a percentage
- **drct**: Wind Direction in degrees from north  
- **sknt**: Wind Speed in knots  
- **p01i**: One hour precipitation for the period from the observation time to
  the time of the previous hourly precipitation reset. This varies slightly by
  site. Values are in inches. This value may or may not contain frozen
  precipitation melted by some device on the sensor or estimated by some
  other means. Unfortunately, we do not know of an authoritative database
  denoting which station has which sensor  
- **alti**: Pressure altimeter in inches  
- **mslp**: Sea Level Pressure in millibar  
- **vsby**: Visibility in miles  
- **gust**: Wind Gust in knots  

## Matching ASOS Weather Stations to Counties

It's not enough to simply match each countie's coordinates to the nearest
ASOS weather station. It turns out that there is considerable variation
between stations in how often they report weather conditions. Thus, we aim to
select the station that is nearest to each county whilst taking into
consideration the following:  

1. Missingness in measurements (temp, humidity, dew point)
2. Missingness in dates of data collection  

Therefore, it's not always the case that the **neareast** ASOS weather station
will be matched to each county. Instead, the 3 nearest stations are considered
and selected based on the critera above. Distance between county coordinates
and the selected weather station is recorded via the `dist_km` column in the
final output data set.