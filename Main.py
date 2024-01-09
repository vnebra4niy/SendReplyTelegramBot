# Import necessary libraries
import telebot
import imaplib
import email
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

user_state = {}
# Initialization of the Telegram bot
bot = telebot.TeleBot('bot-token')

# Create a keyboard
keyboard = telebot.types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
button_send_messages = telebot.types.KeyboardButton('Send Initial Messages')
button_send_replies = telebot.types.KeyboardButton('Send Replies')
keyboard.add(button_send_messages, button_send_replies)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Hello! Choose an action:", reply_markup=keyboard)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id

    if message.text == 'Send Initial Messages':
        # Handling the "send initial messages" command
        bot.send_message(chat_id, "Please enter your Google account login:password in the format 'login:password'.")
        bot.register_next_step_handler(message, get_google_credentials)

    elif message.text == 'Send Replies':
        # Handling the "send replies" command
        bot.send_message(chat_id, "Enter your email login:password in the format 'login:password'.")
        bot.register_next_step_handler(message, get_email_credentials_for_replies)

    else:
        bot.send_message(chat_id, "Please choose an action using the keyboard buttons.", reply_markup=keyboard)

# Handler for the "send initial messages" command
@bot.message_handler(commands=['Send Initial Messages'])
def send_messages(message):
    chat_id = message.chat.id

    # Request Google account login and password
    bot.send_message(chat_id, "Please enter your Google account login:password in the format 'login:password'.")
    bot.register_next_step_handler(message, get_google_credentials)

def get_google_credentials(message):
    chat_id = message.chat.id
    login_password = message.text.split(':')

    if len(login_password) != 2:
        bot.send_message(chat_id, "Incorrect format. Please enter login:password in the format 'login:password'.")
        bot.register_next_step_handler(message, get_google_credentials)
        return

    login, password = login_password

    bot.send_message(chat_id, "Please enter the email subject.")
    bot.register_next_step_handler(message, get_email_subject, login, password)

def get_email_subject(message, login, password):
    chat_id = message.chat.id
    email_subject = message.text

    bot.send_message(chat_id, "Please enter the message text.")
    bot.register_next_step_handler(message, get_email_text, login, password, email_subject)

def get_email_text(message, login, password, email_subject):
    chat_id = message.chat.id
    email_text = message.text

    bot.send_message(chat_id, "Please send a txt file with recipient addresses.")
    bot.register_next_step_handler(message, get_recipient_list, login, password, email_subject, email_text)

def get_recipient_list(message, login, password, email_subject, email_text):
    chat_id = message.chat.id

    try:
        if message.content_type == "document":
            file_info = bot.get_file(message.document.file_id)
            file_path = file_info.file_path
            downloaded_file = bot.download_file(file_path)

            with open("recipient_list.txt", "wb") as f:
                f.write(downloaded_file)

            # Send a message before calling send_emails
            bot.send_message(chat_id, "Messages will start sending.")
            errors = send_emails(login, password, email_subject, email_text, "recipient_list.txt", chat_id)

            if errors:
                error_message = "\n".join(errors)
                bot.send_message(chat_id, f"Errors occurred while sending messages:\n{error_message}")
            else:
                bot.send_message(chat_id, "All messages have been successfully sent.")
        else:
            bot.send_message(chat_id, "Please send a txt file with recipient addresses.")
            bot.register_next_step_handler(message, get_recipient_list, login, password, email_subject, email_text)
    except Exception as e:
        bot.send_message(chat_id, f"Error uploading file: {str(e)}")

# Function for sending email messages
def send_emails(login, password, email_subject, email_text, recipient_list_file, chat_id):
    try:
        # Open the file with recipient addresses
        with open(recipient_list_file, "r") as file:
            recipients = file.read().splitlines()

        errors = []  # List to store errors

        # Send messages with a delay of 0.5 seconds
        for recipient in recipients:
            email_message = create_email(recipient, email_subject, email_text)
            send_result = send_email(login, password, email_message, chat_id, recipient)

            time.sleep(0.5)

        return errors  # Return the list of errors
    except Exception as e:
        return [f"Error sending messages: {str(e)}"]

# Function for creating an email message
def create_email(recipient, subject, body):
    message = MIMEMultipart()
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    return message

# Function for sending an email message
def send_email(login, password, message, chat_id, recipient):
    try:
        message = message.as_string()
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(login, password)
        smtp_server.sendmail(login, recipient, message)
        smtp_server.quit()
    except Exception as e:
        bot.send_message(chat_id, f"Error sending message: {str(e)}")

# Handler for the "send replies" command
@bot.message_handler(commands=['send_replies'])
def send_replies(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Enter your email login:password in the format login:password.")
    bot.register_next_step_handler(message, get_email_credentials_for_replies)

def get_email_credentials_for_replies(message):
    chat_id = message.chat.id
    login_password = message.text.split(':')

    if len(login_password) != 2:
        bot.send_message(chat_id, "Incorrect format. Please enter data in the format login:password.")
        bot.register_next_step_handler(message, get_email_credentials_for_replies)
        return

    login, password = login_password

    bot.send_message(chat_id, "Please enter the reply text.")
    bot.register_next_step_handler(message, send_replies_to_unread_messages, login, password)

def send_replies_to_unread_messages(message, login, password):
    chat_id = message.chat.id
    reply_text = message.text

    unread_messages = get_unread_messages(login, password)

    if not unread_messages:
        bot.send_message(chat_id, "No unread messages.")
        return

    smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
    smtp_server.starttls()
    smtp_server.login(login, password)

    sent_count = 0  # Added: variable to track the number of sent replies

    for message in unread_messages:
        sender_email = message['From']
        original_subject = message['Subject']
        send_reply(login, password, sender_email, original_subject, reply_text)
        sent_count += 1  # Added: increment the counter when sending a reply

    smtp_server.quit()
    bot.send_message(chat_id, f"{sent_count} replies to unread messages sent.")  # Added: display the number of sent replies

def get_unread_messages(login, password):
    try:
        imap_server = imaplib.IMAP4_SSL('imap.gmail.com')
        imap_server.login(login, password)
        imap_server.select('inbox')
        status, email_ids = imap_server.search(None, '(UNSEEN)')

        email_list = email_ids[0].split()
        unread_messages = []

        for email_id in email_list:
            status, msg_data = imap_server.fetch(email_id, '(RFC822)')
            msg = email.message_from_bytes(msg_data[0][1])
            unread_messages.append(msg)

        imap_server.logout()

        return unread_messages
    except Exception as e:
        return []

def send_reply(login, password, recipient, subject, reply_text):
    try:
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(login, password)

        reply_message = create_email(recipient, subject, reply_text)
        smtp_server.sendmail(login, recipient, reply_message.as_string())

        smtp_server.quit()
    except Exception as e:
        print(f"Error sending message to {recipient}: {str(e)}")

def create_email(recipient, subject, body):
    message = MIMEMultipart()
    message["To"] = recipient
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))
    return message

bot.polling(none_stop=True)