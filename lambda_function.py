import json
import boto3
import pytz
import email

from sms_spam_classifier_utilities import one_hot_encode
from sms_spam_classifier_utilities import vectorize_sequences
vocabulary_length = 9013

s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

ENDPOINT_NAME = 'SAGEMAKER_ENDPOINT'
runtime = boto3.client('runtime.sagemaker')

def lambda_handler(event, context):
    print("DEBUG event:", event)
    s3_info = event['Records'][0]['s3']
    bucket_name = s3_info['bucket']['name']
    key_name = s3_info['object']['key']
    
    
    # get the email in S3
    s3_response = s3_client.get_object(
        Bucket=bucket_name,
        Key=key_name,
    )
    print('DEBUG s3_response:', s3_response)
    
    email_string = s3_response['Body'].read().decode('utf-8')
    msg = email.message_from_string(email_string)
    received_from = msg["from"]
    email_subject = msg["subject"]
    
    #reading the body part of msg
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
    
            # skip any text/plain (txt) attachments
            if ctype == "text/plain" and "attachment" not in cdispo:
                email_payload = part.get_payload(decode=True)  # decode
                break
    else:
        email_payload = msg.get_payload(decode=True)
    
    email_body_string = email_payload.decode("utf-8")
    body_arr = email_body_string.splitlines()
    print("DEBUG body_arr:", body_arr)
    print("DEBUG received_from:", received_from)
    print("DEBUG email_subject:", email_subject)
    
    body_string_to_check = ' '.join(body_arr)
    print("DEBUG body_string_to_check:", body_string_to_check)
    body_string_to_send = '\n'.join(body_arr)
    body_string_to_send = body_string_to_send[:240]

    
    # vectorizing message
    test_messages = [body_string_to_check]
    one_hot_test_messages = one_hot_encode(test_messages, vocabulary_length)
    encoded_test_messages = vectorize_sequences(one_hot_test_messages, vocabulary_length)
    json_message = json.dumps(encoded_test_messages.tolist())
    
    # send vectorized message to sage maker
    sagemaker_response = runtime.invoke_endpoint(EndpointName = ENDPOINT_NAME,
                                                 ContentType = "application/json",
                                                 Body = json_message)
    
    decoded_sagemaker_response = json.loads(sagemaker_response['Body'].read().decode())
    print("DEBUG decoded_sagemaker_response:", decoded_sagemaker_response)
    
    classification_number = decoded_sagemaker_response['predicted_label'][0][0]
    if classification_number == 0.0:
        classification = 'HAM'
    elif classification_number == 1.0:
        classification = 'SPAM'
    classification_confidence_score = decoded_sagemaker_response['predicted_probability'][0][0] * 100
    print("DEBUG classification:", classification)
    print("DEBUG classification_confidence_score:", classification_confidence_score)
    
    # write reponse email
    email_time = s3_response['LastModified']

    
    # create both timezone objects
    curr_tz = pytz.timezone("US/Eastern")
    curr_tz_time = email_time.astimezone(curr_tz)

    
    subject = f'Spam Indentification of email "{email_subject}"'
    body = f'''
    We received your email sent at {curr_tz_time.ctime()} with the subject "{email_subject}".
        
    Here is a 240 character sample of the email body:
    {body_string_to_send}
        
    The email was categorized as {classification} with a {classification_confidence_score}% confidence.
    '''
    
    # send response email
    try:
        response = ses_client.send_email(
            Destination={
                'ToAddresses': [
                    received_from,
                ],
            },
            Message={
                'Body': {
                    'Text': {
                        'Charset': 'UTF-8',
                        'Data': body,
                    },
                },
                'Subject': {
                    'Charset': 'UTF-8',
                    'Data': subject,
                },
            },
            Source='no-reply@jin-gyu-lee.me',
        )
    except ClientError as e:
        print("DEBUG error:", e.response['Error'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])