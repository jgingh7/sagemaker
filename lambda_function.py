import json
import boto3
import datetime
import pytz


s3_client = boto3.client('s3')
ses_client = boto3.client('ses')

def lambda_handler(event, context):
    print("DEBUG event:", event)
    s3_info = event['Records'][0]['s3']
    bucket_name = s3_info['bucket']['name'] #emailbucketts
    key_name = s3_info['object']['key'] #i9n26937lh0272713uqlo04f13kqocmjsei3c201
    
    s3_response = s3_client.get_object(
        Bucket=bucket_name,
        Key=key_name,
    )
    print('DEBUG s3_response:', s3_response)
    
    email_string = s3_response['Body'].read().decode('utf-8')
    email_arr = email_string.splitlines()
    
    email_subject = ""
    received_from = ""
    from_idx = 0
    for i, line in enumerate(email_arr):
        if line.startswith('Subject:'):
            email_subject = line[9:]
        elif line.startswith('From:'):
            received_from = line[6:]
        elif line.startswith('X-SES-Outgoing'):
            from_idx = i + 1
        
        if email_subject and received_from and from_idx:
            break
            
    body_arr = email_arr[from_idx:]
    print("DEBUG body_arr:", body_arr)
    
    body_string_to_check = ' '.join(body_arr)
    print("DEBUG body_string_to_use:", body_string_to_check)
    body_string_to_send = '\n'.join(body_arr)
    body_string_to_send = body_string_to_send[:240]
    
    # use prediction endpoint(I think this comes from sage maker)
    
    
    eamil_time = s3_response['LastModified']

    
    # create both timezone objects
    curr_tz = pytz.timezone("US/Eastern")
    curr_tz_time = eamil_time.astimezone(curr_tz)

    
    subject = "Hi"
    body = f'''
        We received your email sent at {curr_tz_time.ctime()} with the
        subject "{email_subject}".
        
        Here is a 240 character sample of the email body:
        {body_string_to_send}
        
        The email was categorized as [CLASSIFICATION] with a
        [CLASSIFICATION_CONFIDENCE_SCORE]% confidence.
    '''
    
    try:
        #Provide the contents of the email.
        response = client.send_email(
            Destination={
                'ToAddresses': [
                    'noreply@jin-gyu-lee.me',
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
            Source='noreply@jin-gyu-lee.me',
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print("DEBUG error:", e.response['Error'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])