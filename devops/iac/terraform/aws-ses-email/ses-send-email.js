// ses-send-email.js
const { SESClient, SendEmailCommand } = require("@aws-sdk/client-ses");

const sesClient = new SESClient({ region: "eu-central-1" });

async function sendEmail() {
  const params = {
    Source: "dariusz.trawicki@dartit.pl", // verified address in SES
    Destination: {
      ToAddresses: ["dt.dartit@gmail.com"],
    },
    Message: {
      Subject: {
        Data: "Hello from AWS SES (Node.js)",
        Charset: "UTF-8",
      },
      Body: {
        Text: {
          Data: "This is a test email sent using AWS SES and Node.js.",
          Charset: "UTF-8",
        },
        // with HTML:
        // Html: {
        //   Data: "<h1>Hello</h1><p>This is a test email.</p>",
        //   Charset: "UTF-8",
        // },
      },
    },
  };

  try {
    const command = new SendEmailCommand(params);
    const response = await sesClient.send(command);
    console.log("Email sent! Message ID:", response.MessageId);
  } catch (err) {
    console.error("Error sending email:", err);
  }
}

sendEmail();
