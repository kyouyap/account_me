output "service_url" {
  value = google_cloud_run_service.service.status[0].url
}

output "service_account_email" {
  value = google_service_account.sa.email
}

output "storage_bucket" {
  value = google_storage_bucket.raw_data.name
}
