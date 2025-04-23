output "service_account_email" {
  value = google_service_account.sa.email
}

output "storage_bucket" {
  value = google_storage_bucket.raw_data.name
}
