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

# Spreadsheet用サービスアカウント
resource "google_service_account" "spreadsheet" {
  account_id   = "spreadsheet-sa"
  display_name = "Spreadsheet Service Account"
}

resource "google_service_account_key" "spreadsheet" {
  service_account_id = google_service_account.spreadsheet.name
}

resource "google_project_iam_member" "spreadsheet_roles" {
  for_each = toset([
    "roles/storage.objectCreator",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
    "roles/secretmanager.secretAccessor"
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.spreadsheet.email}"
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
  delete_contents_on_destroy = true
}

# BigQueryテーブル（家計簿データ）
resource "google_bigquery_table" "household_data" {
  dataset_id = google_bigquery_dataset.moneyforward.dataset_id
  table_id   = "household_data"
  
  schema = file("${path.module}/schema/household_data.json")
  
  clustering = ["date", "major_category", "sub_category"]

  deletion_protection = false
}

# BigQueryテーブル（資産データ）
resource "google_bigquery_table" "assets_data" {
  dataset_id = google_bigquery_dataset.moneyforward.dataset_id
  table_id   = "assets_data"
  
  schema = file("${path.module}/schema/assets_data.json")
  
  clustering = ["date"]

  deletion_protection = false
}

# Spreadsheet Credential Secret
resource "google_secret_manager_secret" "spreadsheet_credential" {
  secret_id = "spreadsheet-credential"
  replication {
  auto {}
}
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "spreadsheet_credential" {
  secret      = google_secret_manager_secret.spreadsheet_credential.id
  secret_data = base64decode(google_service_account_key.spreadsheet.private_key)
}

# Gmail API 認証情報
resource "google_secret_manager_secret" "gmail_api_credentials" {
  secret_id = "gmail-api-credentials"
  replication {
  auto {}
}
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "gmail_api_credentials" {
  secret      = google_secret_manager_secret.gmail_api_credentials.id
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

resource "google_secret_manager_secret_version" "gmail_token" {
  secret      = google_secret_manager_secret.gmail_token.id
  secret_data = var.gmail_token_json != "" ? var.gmail_token_json : "{}"
}
