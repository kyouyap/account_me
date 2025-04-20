# APIの有効化
locals {
  required_apis = [
    "storage.googleapis.com",
    "bigquery.googleapis.com",
    "secretmanager.googleapis.com",
    "gmail.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each                   = toset(local.required_apis)
  project                    = var.project_id
  service                    = each.value
  disable_dependent_services = true
  disable_on_destroy         = false
}

# サービスアカウント
resource "google_service_account" "sa" {
  account_id   = "${var.service_name}-sa"
  display_name = "MoneyForward ETL Pipeline Service Account"
}

resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
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
  depends_on = [google_project_service.apis]
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
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "mf_password" {
  secret      = google_secret_manager_secret.mf_password.id
  secret_data = var.mf_password
}

# Spreadsheet Key Secret
resource "google_secret_manager_secret" "spreadsheet_key" {
  secret_id = "spreadsheet-key"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "spreadsheet_key" {
  secret      = google_secret_manager_secret.spreadsheet_key.id
  secret_data = var.spreadsheet_key
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

# Gmail API 認証情報
resource "google_secret_manager_secret" "gmail_credentials" {
  secret_id = "gmail-api-credentials"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "gmail_credentials" {
  secret      = google_secret_manager_secret.gmail_credentials.id
  # 外部ファイルから認証情報を読み込む
  # 従来のJSON文字列変数が空でない場合はそちらを優先（後方互換性のため）
  secret_data = var.gmail_credentials_json != "" ? var.gmail_credentials_json : file(var.gmail_credentials_file)
}

# Gmail API トークン
resource "google_secret_manager_secret" "gmail_token" {
  secret_id = "gmail-api-token"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}