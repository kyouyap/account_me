variable "project_id" {
  description = "GCPプロジェクトID"
  type        = string
}

variable "region" {
  description = "デプロイするリージョン"
  type        = string
  default     = "asia-northeast1"
}

variable "mf_email" {
  description = "MoneyForwardログインメール"
  type        = string
  sensitive   = true
}

variable "mf_password" {
  description = "MoneyForwardログインパスワード"
  type        = string
  sensitive   = true
}

variable "service_name" {
  description = "Cloud Runサービス名"
  type        = string
  default     = "moneyforward-etl"
}

variable "spreadsheet_key" {
  description = "Google Spreadsheetのキー"
  type        = string
  sensitive   = true
}
