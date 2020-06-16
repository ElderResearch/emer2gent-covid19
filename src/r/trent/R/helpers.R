# Utility functions across notebooks

suppressPackageStartupMessages({
  packages <- c(
    "magrittr", 
    "tidyverse",
    "rsample",
    "furrr",
    "yardstick",
    "assertthat",
    "glue",
    "glmmTMB"
  )
  
  # Warn the user if these packages are loaded by surprise.
  for (pkg in packages) {
    if (!isNamespaceLoaded(pkg)) {
      message(sprintf("Package '%s' is being loaded in helpers.R", pkg))
    }
    library(pkg, character.only = T)
  }
})


# Modeling utilities --------------------------------------------------------------

#' Run a glmmTMB model via 5-fold cross-validation
#'
#' Per fold, this returns:
#'  - the model object
#'  - a coefficients table
#'  - model summary table
#'  - training performance metrics
#'  - testing performance metrics
#'  - the held-out testing data (for, e.g., plotting)
run_model_vfold <- function(formula, data, ziformula = ~0, seed = NULL, folds = 5L) {
  if (!is.null(seed))
    set.seed(seed)
  
  group_vfold_cv(data, group = county_fip, v = folds) %>% 
    future_pmap_dfr(~ {
      tr <- training(.x)
      te <- assessment(.x)
      id <- .y
      
      message("Running fold: ", id)
      
      model <- glmmTMB(
        formula, 
        data = tr,
        family = glmmTMB::nbinom2(), 
        ziformula = ziformula)
      
      pred_tr <- predict(model, tr, type = "conditional")
      pred_te <- predict(model, te, type = "conditional", allow.new.levels	= T)
      
      metrics_tr <- tribble(
        ~ metric, ~ value,
        "ccc",    ccc_vec(tr$target, pred_tr), 
        "huber",  huber_loss_vec(tr$target, pred_tr), 
        "mae",    mae_vec(tr$target, pred_tr), 
        "rsq",    rsq_vec(tr$target, pred_tr)
      )
      
      metrics_te <- tribble(
        ~ metric, ~ value,
        "ccc",    ccc_vec(te$target, pred_te), 
        "huber",  huber_loss_vec(te$target, pred_te), 
        "mae",    mae_vec(te$target, pred_te), 
        "rsq",    rsq_vec(te$target, pred_te)
      )
  
      tibble(
        id = id,
        object = list(model),
        tidy = list(suppressMessages(broom.mixed:::tidy.glmmTMB(model))),
        glance = list(suppressMessages(broom.mixed:::glance.glmmTMB(model))),
        train = list(metrics_tr),
        test = list(metrics_te),
        test_data = list(te)
      )
  })
}


#' Cache and read an operation from disk
cache_operation <- function(path, ...) {
  if (!exists("FORCE_MODEL_RUN")) FORCE_MODEL_RUN <- FALSE
  if (!file.exists(path) | FORCE_MODEL_RUN) {
    cat("Operation not cached; executing now\n")
    saveRDS(..., path)
  } else {
    cat("Loading operation from cache:\n")
    cat(glue("{path}\n"))
  }
  return(readRDS(path))
}


# Cross-validation tools ----------------------------------------------------------

#' Extract model performance (train and test) from table(s) of CV results
#' If necessary, aggregate assuming independent errors.
extract_cv_perf <- function(...) {
  input_names <- map_chr(rlang::exprs(...), as.character)
  inputs <- list(...)
  
  map2_dfr(inputs, input_names, ~ {
    .df <- .x
    .name <- .y
    out <- imap_dfr(purrr::set_names(c("train", "test")), ~ {
      .df %>%
        select(id, all_of(.x)) %>%
        unnest(all_of(.x)) %>%
        mutate(partition = .y, .before = everything())
      }) %>% 
      group_by(partition, metric) %>%
      summarize(mean = mean(value), sd = sd(value), .groups = "drop") %>%
      pivot_wider(
        id_cols = "metric",
        names_from = "partition",
        values_from = c("mean", "sd")
      ) %>%
      relocate(ends_with("train"), .after = "metric")
      if (.name != ".") out <- mutate(out, model = .name, .after = "metric")
    out
    }) %>% 
    arrange(metric)
}


#' Extract model summary data from table(s) of CV results
#' If necessary, aggregate assuming independent errors.
extract_cv_glance <- function(...) {
  input_names <- map_chr(rlang::exprs(...), as.character)
  inputs <- list(...)
  map2_dfr(inputs, input_names, ~ {
    out <- .x %>% 
      select(id, glance) %>% 
      unnest(glance) %>% 
      pivot_longer(-id, names_to = "metric") %>% 
      group_by(metric) %>% 
      summarize(mean = mean(value), sd = sd(value), .groups = "drop")
    if (.y != ".") out <- mutate(out, model = .y, .after = "metric")
    out
    }) %>% 
    arrange(metric)
}


#' Extract model coefficients from table(s) of CV results
#' If necessary, aggregate assuming independent errors.
extract_cv_tidy <- function(...) {
  input_names <- map_chr(rlang::exprs(...), as.character)
  inputs <- list(...)
  map2_dfr(inputs, input_names, ~ {
    out <- .x %>% 
      select(id, tidy) %>% 
      unnest(tidy) %>% 
      group_by(effect, component, group, term) %>% 
      summarize(
        estimate = mean(estimate),
        std.error = sqrt(sum(std.error**2)),
        .groups = "drop"
      )
    if (.y != ".") out <- mutate(out, model = .y, .before = "estimate")
    out
    }) %>% 
    arrange(estimate)
}

#' Extract samples county-level predictions from a CV fit object
extract_cv_trajectories <- function(data, .per_fold = 1L, seed = NULL) {
  if (!is.null(seed)) set.seed(seed)
  future_pmap_dfr(data, ~ {
    model <- ..2
    data  <- ..7
    
    # Sample random counties, then predict with the model
    data %>% 
      distinct(county_fip) %>% 
      sample_n(.per_fold) %>% 
      semi_join(data, ., by = "county_fip") %>%
      mutate(
        yhat = predict(model, ., allow.new.levels = T, type = "response")
      )
  })
}


# Plotting helpers ----------------------------------------------------------------

#' Show a model fit overlaid with policy windows
plot_w_policy <- function(data) {
  boxes <- data %>% 
    group_by(state, county, policy_recoded) %>% 
    summarize(start = min(date), end = max(date), .groups = "drop")
  
  data %>% 
    select(date, state, county, target, policy_recoded, yhat) %>% 
    pivot_longer(c(target, yhat)) %>% 
    ggplot() + 
    geom_rect(
      aes(xmin = start, xmax = end, ymin = -Inf, ymax = Inf, fill = policy_recoded), 
      data = boxes
    ) + 
    geom_line(aes(date, value, alpha = name, size = name)) +
    facet_wrap(~ state + county, scales = "free") + 
    scale_size_manual(values = c(0.5, 0.8)) + 
    scale_alpha_manual(values = c(0.6, 1)) + 
    scale_fill_viridis_d(alpha = 0.3)
}

#' Nicely plot a Boruta object
plot_boruta <- function(boruta_obj) {
  decisions <- enframe(boruta_obj$finalDecision, "feature", "decision")
  decisions$decision <- as.character(decisions$decision)
  
  boruta_obj$ImpHistory %>% 
    as_tibble(rownames = "iteration") %>% 
    pivot_longer(-iteration, names_to = "feature", values_to = "importance") %>% 
    filter(importance > -Inf) %>% 
    left_join(decisions, by = "feature") %>% 
    mutate(
      decision = factor(
        replace_na(decision, "Permuted"), 
        levels = c("Confirmed", "Tentative", "Rejected", "Permuted")
    )) %>% 
    mutate(feature = (fct_reorder(factor(feature), importance, median))) %>% 
    ggplot(aes(feature, importance, fill = decision)) + 
    geom_boxplot() + 
    coord_flip() + 
    labs(y = "Importance", x = NULL) + 
    scale_fill_manual(
      name = "Outcome", 
      values = c(
        "Confirmed" = "#00cc66", 
        "Tentative" = "#f0e68c", 
        "Permuted" = "#99aaaa",
        "Rejected" = "#cc0066"
      )
    )
}

#' Bind all coefficients together in one table at the state level
get_state_coefs <- function(model, re_plot) {
  fe_coef <- broom.mixed::tidy(model)
  re_coef <- as_tibble(re_plot[[2]]$data)
}

#' Bind all coefficients together in one table at the county level
get_county_coefs <- function(model, re_plot) {
  fe_coef <- broom.mixed::tidy(model)
  re_coef <- as_tibble(re_plot[[1]]$data)
}

#' Plot the average effect over time for one or more counties

#' Plot the average effect over time for one or more states

#' Plot the average interaction between policy and time

#' Plot the average county profile
#' Average length, average time of policy, etc.
#' Most coefficients are zero, except the dynamic ones

#' Plot the average county profile without any policy

#' Plot the average county profile with counterfactuals


# ABT preparation -----------------------------------------------------------------

#' Measure the number of days since the first reported infection
abt_fe_time_days_since_inf1 <- function(abt) {
  out <- abt %>% 
    group_by(state_code, county_fip) %>% 
    arrange(state_code, county_fip, date) %>% 
    mutate(time_days_since_inf1 = suppressWarnings(
      as.integer(date - min(date[confirmed > 0]))
    )) %>% 
    ungroup() %>% 
    mutate(time_days_since_inf1 = if_else(
      is.na(time_days_since_inf1) | time_days_since_inf1 < 0, 
      -1L, 
      time_days_since_inf1
    ))
  
  assert_that(nrow(abt) == nrow(out))
  assert_that(all(!is.na(out$time_days_since_inf1)))
  
  out
}


#' Transform median income to units of $10K
abt_fe_acs_median_hh_inc_10k <- function(abt) {
  out <- abt %>% 
    mutate(
      acs_median_hh_inc_10k = acs_median_hh_inc_total / 10000,
      .after = acs_median_hh_inc_total,
      .keep = "unused"
    )
  
  assert_that(all(dim(abt) == dim(out)))
  assert_that(all(!is.na(out$acs_median_hh_inc_10k)))
  
  out
}


#' Add positive COV-19 test fraction to the ABT
abt_fe_add_cov_pos_tests_frac <- function(abt) {
  out <- abt %>% 
    mutate(cov_pos_tests_frac = if_else(
      cov_total_tests == 0,
      0,
      cov_pos_tests / cov_total_tests)
    )
  
  assert_that(sum(is.na(out$cov_pos_tests_frac)) == 0)
  assert_that(max(out$cov_pos_tests_frac) <= 1.00001)
  assert_that(min(out$cov_pos_tests_frac) >= 0)
  
  out
}


#' Add two coarse age columns to the ABT
#' 
#' * 25-54
#' * 55-84
abt_fe_add_coarse_age_bins <- function(abt) {
  out <- abt %>% 
    mutate(
      acs_age_25_54 = acs_age_25_34 + acs_age_35_44 + acs_age_45_54,
      acs_age_55_84 = acs_age_55_64 + acs_age_65_74 + acs_age_75_84
    )
  
  assert_that(sum(is.na(out$acs_age_25_54)) == 0)
  assert_that(min(out$acs_age_25_54) >= 0 & max(out$acs_age_25_54) <= 1)
  assert_that(min(out$acs_age_55_84) >= 0 & max(out$acs_age_55_84) <= 1)
  
  out
}


#' Add a "time in phase" column
abt_fe_add_time_phase <- function(abt) {
  out <- abt %>% 
    group_by(county_fip, policy) %>% 
    mutate(time_phase = as.integer(date - min(date))) %>% 
    ungroup()
  
  assert_that(all(!is.na(out$time_phase)))
  assert_that(min(out$time_phase) == 0)
  
  out
}


#' Add circle-encoded DOW
abt_fe_add_circle_enc_dow <- function(abt) {
  out <- abt %>% 
    mutate(
      time_dow_x = cos(2 * pi * (as.integer(time_dow) - 1) / 7),
      time_dow_y = sin(2 * pi * (as.integer(time_dow) - 1) / 7),
      .keep = "unused",
      .after = "time_dow"
    )
  
  assert_that(all(!is.na(c(out$time_dow_x, out$time_dow_y))))
  assert_that(all(abs(out$time_dow_x) <= 1))
  assert_that(all(abs(out$time_dow_y) <= 1))
  
  out
}


#' Standardize a feature @ 2-sigma
standardize <- function(values) {
  (values - mean(values)) / (2 * sd(values))
}


#' Rank normalization
rank_norm <- function(values) {
  # -1, +1 keeps qnorm from getting a value of 1
  ranks <- rank(values, ties.method = "average") - 1
  qnorm(ranks / max(ranks + 1))
}
