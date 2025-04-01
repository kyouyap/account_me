# APIの有効化
locals {
  required_apis = [
    "run.googleapis.com",
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "cloudscheduler.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com"
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.required_apis)
  project  = var.project_id
  service  = each.value
}

# サービスアカウント
resource "google_service_account" "sa" {
  account_id   = "${var.service_name}-sa"
  display_name = "MoneyForward ETL Pipeline Service Account"
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
    "roles/run.invoker",
    "roles/storage.objectCreator",
    "roles/bigquery.dataEditor",
    "roles/secretmanager.secretAccessor"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.sa.email}"
}

# Secret Manager
resource "google_secret_manager_secret" "mf_email" {
  secret_id = "mf-email"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "mf_email" {
  secret      = google_secret_manager_secret.mf_email.id
  secret_data = var.mf_email
}

resource "google_secret_manager_secret" "mf_password" {
  secret_id = "mf-password"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "mf_password" {
  secret      = google_secret_manager_secret.mf_password.id
  secret_data = var.mf_password
}

# Storage
resource "google_storage_bucket" "raw_data" {
  name          = "mf-raw-data-${var.project_id}"
  location      = var.region
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
}

# BigQuery
resource "google_bigquery_dataset" "moneyforward" {
  dataset_id    = "moneyforward"
  friendly_name = "MoneyForward Dataset"
  location      = var.region
}

# Artifact Registry
resource "google_artifact_registry_repository" "repo" {
  repository_id = var.service_name
  format        = "DOCKER"
  location      = var.region
}

# Cloud Run
resource "google_cloud_run_service" "service" {
  name     = var.service_name
  location = var.region

  template {
    spec {
      service_account_name = google_service_account.sa.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.service_name}/scraper:v1"
        resources {
          limits = {
            memory = "2Gi"
          }
        }
      }
      timeout_seconds = 1800
    }
  }

  depends_on = [google_project_service.apis]
}

# Cloud Scheduler
resource "google_cloud_scheduler_job" "job" {
  name        = "${var.service_name}-daily"
  description = "Daily MoneyForward ETL Pipeline"
  schedule    = "0 1 * * *"
  time_zone   = "Asia/Tokyo"

  http_target {
    http_method = "POST"
    uri         = google_cloud_run_service.service.status[0].url

    oidc_token {
      service_account_email = google_service_account.sa.email
    }
  }

  depends_on = [google_project_service.apis]
}
