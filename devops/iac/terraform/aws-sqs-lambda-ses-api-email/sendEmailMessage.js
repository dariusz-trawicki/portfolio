// sendEmailMessage.js  (CommonJS)

const { SQSClient, SendMessageCommand } = require("@aws-sdk/client-sqs");

const AWS_REGION = process.env.AWS_REGION;
const QUEUE_URL = process.env.QUEUE_URL;

if (!AWS_REGION) {
  throw new Error("AWS_REGION environment variable is not set");
}

if (!QUEUE_URL) {
  throw new Error("QUEUE_URL environment variable is not set");
}

const sqsClient = new SQSClient({ region: AWS_REGION });

async function sendMessage() {
  const messageBody = {
    to: "dt.dartit@gmail.com",
    subject: "Test from SQS -> Lambda -> SES",
    body: "Hi! This email is being sent through the SQS queue and Lambda :)",
  };

  const params = {
    QueueUrl: QUEUE_URL,
    MessageBody: JSON.stringify(messageBody),
  };

  try {
    const command = new SendMessageCommand(params);
    const response = await sqsClient.send(command);
    console.log("Message sent! ID:", response.MessageId);
  } catch (err) {
    console.error("Error sending message:", err);
  }
}

sendMessage();
