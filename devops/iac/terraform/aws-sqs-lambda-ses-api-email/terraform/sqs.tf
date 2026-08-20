#############################
# SQS queue
#############################

resource "aws_sqs_queue" "email_queue" {
  name                       = "email-send-queue"
  visibility_timeout_seconds = 60 # must be > Lambda timeout
  message_retention_seconds  = 345600
}