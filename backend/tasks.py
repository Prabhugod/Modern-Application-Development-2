#Importing the worker
# from workers import celery
from celery.schedules import crontab
from models import Users,ServiceProfessionals,db,Services,ServiceRequests
from config import send_email
from app import celery
from sqlalchemy import and_,func
# import csv
# import os
# from datetime import datetime


@celery.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        # crontab(minute=0, hour=16),
        crontab(),
        daily_reminder.s(),
        name = "daily reminder"
    )

    sender.add_periodic_task(
        crontab(),
        # crontab(0, 0, day_of_month = 1),
        monthly_report.s(),
        name = "montly report"
    )


@celery.task()
def daily_reminder():
    # Fetch verified service professionals
    verified_service_professionals = (
        db.session.query(Users, ServiceProfessionals)
        .join(ServiceProfessionals, Users.user_id == ServiceProfessionals.user_id)
        .filter(
            and_(
                Users.role == 'service_professional',
                ServiceProfessionals.is_verified == True
            )
        )
        .all()
    )

    # HTML Template for the email
    html_template = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Daily Reminder</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                color: #333;
                margin: 0;
                padding: 0;
            }
            .container {
                max-width: 600px;
                margin: 20px auto;
                background-color: #ffffff;
                border: 1px solid #ddd;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            }
            .header {
                background-color: #4CAF50;
                color: white;
                padding: 20px;
                text-align: center;
                font-size: 24px;
            }
            .content {
                padding: 20px;
            }
            .content p {
                line-height: 1.6;
                margin-bottom: 20px;
            }
            .action-btn {
                display: inline-block;
                margin: 10px 0;
                padding: 10px 20px;
                background-color: #4CAF50;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                font-size: 16px;
            }
            .action-btn:hover {
                background-color: #45a049;
            }
            .footer {
                text-align: center;
                padding: 15px;
                font-size: 12px;
                color: #777;
                background-color: #f9f9f9;
                border-top: 1px solid #ddd;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                Daily Reminder
            </div>
            <div class="content">
                <p>Dear [Service Professional],</p>
                <p>This is a friendly reminder to check your pending service requests. It seems you haven't visited your dashboard or acted upon some service requests recently.</p>
                <p>Please take the necessary actions:</p>
                <ul>
                    <li>Accept or reject the pending requests.</li>
                    <li>Ensure timely service for accepted requests.</li>
                </ul>
                <a href="http://localhost:8080/professional_login" class="action-btn">Visit Dashboard</a>
                <p>If you have any questions or need assistance, feel free to contact support.</p>
                <p>Thank you for your attention!</p>
                <p>Best Regards,<br>A to Z Household Service Team</p>
            </div>
            <div class="footer">
                <p>&copy; 2024 A to Z Household Service. All rights reserved.</p>
                <p>Do not reply to this email. If you need help, contact support at <a href="mailto:support@yourapp.com">support@yourapp.com</a>.</p>
            </div>
        </div>
    </body>
    </html>
    """

    # Send email to each verified service professional
    for user, professional in verified_service_professionals:
        to_email = user.email
        personalized_html = html_template.replace("[Service Professional]", user.username)
        send_email(to=to_email, sub="Your daily reminder", html_content=personalized_html)
        print(f"DAILY REMINDER sent to {to_email}")

    return "DAILY_REMINDER Completed"

@celery.task()
def monthly_report():
    customers = db.session.query(Users).filter_by(role='customer').all()
    for customer in customers:
    # Query services related to the customer
        service_stats = (
            db.session.query(
                Services.name.label('service_name'),
                func.count(ServiceRequests.service_id).filter(ServiceRequests.service_status == 'requested').label('requested'),
                func.count(ServiceRequests.service_id).filter(ServiceRequests.service_status == 'closed').label('completed'),
                func.count(ServiceRequests.service_id).filter(ServiceRequests.service_status == 'assigned').label('assigned'),
                func.count(ServiceRequests.service_id).filter(ServiceRequests.service_status == 'rejected').label('rejected'),
            )
            .join(ServiceRequests, Services.service_id == ServiceRequests.service_id)
            .filter(ServiceRequests.customer_id == customer.user_id)
            .group_by(Services.name)
            .all()
        )
    html_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Monthly Activity Report</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #f4f4f4;
            color: #333;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 20px auto;
            background-color: #ffffff;
            border: 1px solid #ddd;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        .header {
            background-color: #007BFF;
            color: white;
            padding: 20px;
            text-align: center;
            font-size: 24px;
        }
        .content {
            padding: 20px;
        }
        .content p {
            line-height: 1.6;
        }
        .report {
            margin-top: 20px;
            border-collapse: collapse;
            width: 100%;
        }
        .report th, .report td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        .report th {
            background-color: #f2f2f2;
        }
        .footer {
            text-align: center;
            padding: 15px;
            font-size: 12px;
            color: #777;
            background-color: #f9f9f9;
            border-top: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            Monthly Activity Report
        </div>
        <div class="content">
            <p>Dear [Customer Name],</p>
            <p>Here's your activity summary for the past month:</p>
            <table class="report">
                <tr>
                    <th>Service</th>
                    <th>Requested</th>
                    <th>Completed</th>
                    <th>Assigned</th>
                    <th>Rejected</th>
                </tr>
                {service_rows}
            </table>
            <p>Thank you for choosing our platform!</p>
            <p>Best Regards,<br>A to Z Household Service Team</p>
        </div>
        <div class="footer">
            <p>&copy; 2024 A to Z Household Service. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""


    # Generate rows for the HTML table
    service_rows = ''.join(
        f"""
        <tr>
            <td>{stat.service_name}</td>
            <td>{stat.requested}</td>
            <td>{stat.completed}</td>
            <td>{stat.pending}</td>
        </tr>
        """
        for stat in service_stats
    )

    # Replace placeholders in HTML template
    email_content = html_template.replace('[Customer Name]', customer.username)
    email_content = email_content.replace('{service_rows}', service_rows)

    # Send email
    send_email(to=customer.email, sub='Your Monthly Activity Report', html_content=email_content)

    return "Monthly activity reports sent!"


# @celery.task
# def export_service_requests():
#     # Set the directory for saving the exported CSV
#     EXPORT_DIR = os.path.join(os.getcwd(), 'exports')  # You can adjust the path as needed
#     if not os.path.exists(EXPORT_DIR):
#         os.makedirs(EXPORT_DIR)

#     # Fetch all service requests (all statuses)
#     service_requests = ServiceRequests.query.all()

#     # Prepare the file path with timestamp to avoid overwriting
#     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#     file_path = os.path.join(EXPORT_DIR, f'service_requests_{timestamp}.csv')

#     # Open the file and write the CSV content
#     with open(file_path, mode='w', newline='') as file:
#         writer = csv.writer(file)
#         writer.writerow(['Service ID', 'Customer ID', 'Professional ID', 'Date of Request', 'Remarks'])

#         # Write the service request data
#         for request in service_requests:
#             writer.writerow([request.service_id, request.customer_id, request.professional_id, request.date_of_request, request.remarks])

#     return f'CSV export completed. File saved at {file_path}'
