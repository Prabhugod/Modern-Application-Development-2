#importing the required libraries
from flask import Flask, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import app
from sqlalchemy import func
from io import BytesIO
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from models import db, Users, ServiceProfessionals, Services, ServiceRequests, Reviews
from cache import cache

# Creating the decorator for the routes
@app.route('/')
def home():
    # flash('Welcome to the Hosuing Service Application. Please Login to continue.')
    # flash('If you are a new user, please register first.')
    # return render_template('index.html')
    data = request.get_json()
    user_id = data["user_id"]
    username = data["username"]
    name = data["name"]      
    email = data["email"]        
    role = data["role"]        
    date_created = data["date_created"]
    status = data["status"]
    return f"user{username}{user_id}"

#--------------------------------------------------------------------------------------------------------------
#                                        USER CONTROLLER PART
#--------------------------------------------------------------------------------------------------------------

@app.route('/login', methods=['POST'])
def login():
    # Handling the form submission
    data = request.get_json()
    username = data["username"]
    password = data["password"]
    user = Users.query.filter_by(username=username).first()
    
    # If the username or password is empty
    if username == '' or password == '':
        return {"message":"Please fill all the fields and try again"}, 400

    # If the username doesn't exist
    if not user:
        return {"message" : "Please check your Username and try again."}, 400

    # If the username exists, check the password
    if not user.check_password(password):
        return {"message" : "Please check your Password and try again."}, 400

    # If the user is not an admin
    if user.role == 'admin':
        return {"message" : "Kindly login through admin login page"}, 401
    
    if user.role == 'service_professional':
        return {"message" : "Kindly login through service professional login page"}, 401
    
    #Check if the service professional is blocked
    if user.status != 'active':
        return {"message" : "You have blocked by the admin, Kindly contact the Admin."}
    
    # If login is successful
    token = create_access_token(identity=str(user.user_id),additional_claims={"type" : "user", "id": user.user_id})
    return {"access_token" : token, "username": user.username, "user_id": user.user_id, "role": user.role}, 200

@app.route('/register_user', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    name = data.get("name")
    email = data.get("email")
    location = data.get("location")

    # Input validation
    if not all([username, password, name, email, location]):
        return {"message": "Please fill all the required fields."}, 400

    # Check if username or email already exists
    if Users.query.filter_by(username=username).first():
        return {"message": "Username already exists. Please choose another one."}, 400
    if Users.query.filter_by(email=email).first():
        return {"message": "Email already exists. Please use another one."}, 400

    # Create a new user
    new_user = Users(
        username=username,
        password=password,
        name=name,
        email=email,
        location=location
    )

    # Add and commit the new user to the database
    try:
        db.session.add(new_user)
        db.session.commit()
        # Prepare the user data for the response (excluding sensitive data like password)
        user_data = {
            "user_id": new_user.user_id,
            "username": new_user.username,
            "name": new_user.name,
            "email": new_user.email,
            "role": new_user.role,
            "status": new_user.status,
            "date_created": new_user.date_created,
            "location": new_user.location
        }
        return {
            "message": "User registered successfully.",
            "user": user_data
        }, 201
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/user/professionals', methods=['GET'])
def get_user_professionals():
    try:
        # Perform a JOIN to get data from both Users and ServiceProfessionals tables
        professionals = db.session.query(
            Users.user_id,
            Users.name,
            Users.status,
            ServiceProfessionals.service_type,
            ServiceProfessionals.experience,
            ServiceProfessionals.contact_info,
            ServiceProfessionals.is_verified,
            ServiceProfessionals.description
        ).join(
            ServiceProfessionals, ServiceProfessionals.user_id == Users.user_id
        ).filter(
            Users.role == 'service_professional'  # Ensure that the user is a service professional
        ).all()

        # If no professionals are found, return an appropriate message
        if not professionals:
            return jsonify({
                "message": "No service professionals found.",
                "professionals": []
            }), 200

        # Format and return the list of professionals
        return jsonify({
            "message": "Service professionals retrieved successfully.",
            "professionals": [
                {
                    "professional_id": professional.user_id, 
                    "name": professional.name,
                    "service_name": professional.service_type,
                    "experience": professional.experience,
                    "contact_info": professional.contact_info,
                    "is_verified": professional.is_verified,
                    "description": professional.description,
                    "status": professional.status
                }
                for professional in professionals
            ]
        }), 200

    except Exception as e:
        # Handle unexpected errors
        return jsonify({
            "message": f"An error occurred while retrieving service professionals: {str(e)}"
        }), 500

@app.route('/user/search', methods=['GET'])
def search():
    try:
        query = request.args.get('q', '', type=str)  
        
        if not query:
            return jsonify({"error": "Search query is missing"}), 400
        
        # Initialize results dictionary
        results = {
            'services': [],
            'professionals': []
        }

        # Search in Services
        services = Services.query.filter(Services.name.ilike(f'%{query}%')).all()
        for service in services:
            results['services'].append({
                "id": service.service_id,
                "name": service.name,
                "description": service.description,
                "base_price": service.base_price,
                "time_required": service.time_required
            })

        # Search in Service Professionals
        professionals = db.session.query(ServiceProfessionals).join(Users).filter(
        (Users.username.ilike(f'%{query}%')) | (Users.email.ilike(f'%{query}%'))
        ).all()
        for professional in professionals:
            results['professionals'].append({
                "id": professional.professional_id,
                "username": professional.user.username,
                "email": professional.user.email,
                "specialization": professional.service_type
            })

        # If no results are found
        if not any(results.values()):
            return jsonify({"message": f"No results found for '{query}'"}), 404

        # Return the results
        return jsonify({"results": results})

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "An error occurred during the search process"}), 500

@app.route('/services/<int:service_id>/professionals', methods=['GET'])
def get_service_professionals(service_id):
    try:
        # Fetch the service to ensure it exists
        service = Services.query.get(service_id)
        if not service:
            return jsonify({"error": "Service not found"}), 404
        
        # Fetch service requests for the given service_id
        service_requests = ServiceRequests.query.filter_by(service_id=service_id).all()
        
        if not service_requests:
            return jsonify({"error": "No service requests found for this service"}), 404

        # Gather the professional_ids from the service requests
        professional_ids = [request.professional_id for request in service_requests if request.professional_id]
        print(f"Professional IDs: {professional_ids}")  # Debugging line

        if not professional_ids:
            return jsonify({"error": "No professionals assigned to this service"}), 404

        # Fetch the professionals using the professional_ids and join Users and Reviews to get the necessary details
        professionals = db.session.query(
            ServiceProfessionals.professional_id,
            Users.name.label('professional_name'),
            db.func.avg(Reviews.rating).label('avg_rating'),
            ServiceProfessionals.experience,
            ServiceProfessionals.contact_info
        ).join(Users, Users.user_id == ServiceProfessionals.user_id) \
         .outerjoin(Reviews, Reviews.professional_id == ServiceProfessionals.professional_id) \
         .filter(ServiceProfessionals.professional_id.in_(professional_ids)) \
         .group_by(ServiceProfessionals.professional_id) \
         .all()

        print(f"Professionals: {professionals}")  # Debugging line

        if not professionals:
            return jsonify({"error": "No professionals found for this service"}), 404

        # Prepare response data
        professionals_data = [
            {
                "id": prof.professional_id,
                "name": prof.professional_name,
                "rating": round(prof.avg_rating, 2) if prof.avg_rating else 0,
                "experience": prof.experience,
                "contact": prof.contact_info
            } for prof in professionals
        ]

        return jsonify({
            "service": service.name,
            "professionals": professionals_data
        })
    
    except Exception as e:
        app.logger.error(f"Error fetching professionals: {str(e)}")
        return jsonify({"error": "An error occurred", "details": str(e)}), 500

@app.route('/create_service_request/<int:customer_id>', methods=['POST'])
@jwt_required()
def create_service_request(customer_id):
    # Ensure the customer is the one making the request by verifying their user_id from the JWT
    current_user_id = get_jwt_identity()
  
    # Validate if the current user is the same as the customer_id passed in the URL
    if int(current_user_id) != customer_id:
        return {"message": "You are not authorized to create a service request for another customer."}, 403

    # Fetch the request data from the body of the request
    data = request.get_json()
    service_id = data.get('service_id')
    location = data.get('location')
    remarks = data.get('remarks')
    professional_id = data.get('professional_id')

    # Validate that all required fields are provided
    if not service_id or not location or not professional_id:
        return {"message": "Service ID and location are required to create a service request."}, 400

    # Ensure the service exists in the database
    service = Services.query.get(service_id)
    if not service:
        return {"message": "Service not found."}, 404

    # Create the service request record in the database
    new_request = ServiceRequests(
        service_id=service_id,
        customer_id=customer_id,
        location=location,
        remarks=remarks,
        service_status='requested',
        professional_id=professional_id
    )

    # Attempt to add and commit the new service request to the database
    try:
        db.session.add(new_request)
        db.session.commit()
        return {"message": "Service request created successfully."}, 201
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred while creating the service request: {str(e)}"}, 500

@app.route('/edit_service_request/<int:customer_id>/<int:request_id>', methods=['PUT'])
@jwt_required()
def edit_service_request(customer_id, request_id):
    # Get the logged-in user's ID from the JWT
    current_user_id = get_jwt_identity()

    # Check if the logged-in user matches the customer in the URL
    if int(current_user_id) != customer_id:
        return {"message": "You are not authorized to edit this service request."}, 403

    # Find the service request
    service_request = ServiceRequests.query.filter_by(
        request_id=request_id, customer_id=customer_id
    ).first()

    # If the service request does not exist
    if not service_request:
        return {"message": "Service request not found."}, 404

    # Get the request payload
    data = request.get_json()
    remarks = data.get("remarks")
    location = data.get("location")
    service_status = data.get("service_status")
    date_of_completion = data.get("date_of_completion")

    # Update only the fields provided
    if remarks:
        service_request.remarks = remarks
    if location:
        service_request.location = location
    if date_of_completion:
        service_request.date_of_completion = date_of_completion
    if service_status and service_status in ['requested', 'assigned', 'closed']:
        service_request.service_status = service_status

    # Commit changes to the database
    db.session.commit()

    return {
        "message": "Service request updated successfully.",
        "service_request": service_request.to_dict()
    }, 200

@app.route('/delete_service_request/<int:customer_id>/<int:request_id>', methods=['DELETE'])
@jwt_required()  # Ensures that the user is authenticated using JWT
def delete_service_request(customer_id, request_id):
    # Get the logged-in user's ID from the JWT
    current_user_id = get_jwt_identity()

    # Check if the logged-in user matches the customer in the URL
    if int(current_user_id) != customer_id:
        return jsonify({"message": "You are not authorized to delete this service request."}), 403

    # Find the service request for the given customer_id and request_id
    service_request = ServiceRequests.query.filter_by(
        request_id=request_id, customer_id=customer_id
    ).first()

    # If the service request does not exist
    if not service_request:
        return jsonify({"message": "Service request not found."}), 404

    # Delete the service request from the database
    db.session.delete(service_request)
    db.session.commit()

    # Return a response confirming the deletion
    return jsonify({"message": "Service request deleted successfully."}), 200

@app.route('/search_services', methods=['GET'])
@jwt_required()  # Ensure the user is authenticated
def search_services():
    # Retrieve search parameters from the query string
    location = request.args.get('location')
    service_name = request.args.get('service_name')

    # Start building the query based on the provided search criteria
    query = ServiceRequests.query

    # Filter by location if provided
    if location:
        query = query.filter(ServiceRequests.location.ilike(f"%{location}%"))

    # Filter by service name if provided
    if service_name:
        query = query.filter(ServiceRequests.name.ilike(f"%{service_name}%"))

    # Execute the query and get the results
    services = query.all()

    # If no services are found, return a message
    if not services:
        return {"message": "No services found matching the search criteria."}, 404

    # Convert the result to a list of dictionaries
    services_json = [service.to_dict() for service in services]

    # Return the list of services as a JSON response
    return {"services": services_json}, 200


#--------------------------------------------------------------------------------------------------------------
#                                        PROFESSIONAL CONTROLLER PART
#--------------------------------------------------------------------------------------------------------------

@app.route('/register_service_professional', methods=['POST'])
def register_service_professional():
    try:
        # Extract data from the request
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        name = data.get('name')
        email = data.get('email')
        service_type = data.get('service_type')
        experience = data.get('experience')
        contact_info = data.get('contact_info')
        description = data.get('description')
        location = data.get('location')

        # Validate input
        if not (username and password and name and email and service_type and location):
            return jsonify({"error": "Missing required fields"}), 400

        # Check if username or email already exists
        if Users.query.filter((Users.username == username) | (Users.email == email)).first():
            return jsonify({"error": "Username or email already exists"}), 409
        

        # Create a new user
        new_user = Users(
            username=username,
            name=name,
            email=email,
            role='service_professional',
            location=location
        )
        new_user.password = password  

        # Add the user to the database
        db.session.add(new_user)
        db.session.flush()  # Flush to get the user ID

        # Create a service professional profile
        new_service_professional = ServiceProfessionals(
            user_id=new_user.user_id,  
            service_type=service_type,
            experience=experience,
            contact_info=contact_info,
            description=description
        )

        # Add the service professional profile to the database
        db.session.add(new_service_professional)

        # Commit the transaction
        db.session.commit()

        # Return a success response
        return jsonify({
            "message": "Service professional registered successfully",
            "user": new_user.to_dict(),
            "service_professional": new_service_professional.to_dict()
        }), 201

    except Exception as e:
        # Roll back the transaction in case of error
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/login_service_professional', methods=['POST'])
def login_service_professional():
    # Handling the form submission
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    user = Users.query.filter_by(username=username).first()
    
    # If the username or password is empty
    if not username or not password:
        return {"message":"Please fill all the fields and try again"}, 400

    # If the username doesn't exist
    if not user:
        return {"message": "Please check your Username and try again."}, 400

    # If the username exists, check the password
    if not user.check_password(password):
        return {"message": "Please check your Password and try again."}, 400

    # If the user is not a service professional
    if user.role != 'service_professional':
        return {"message": "You are not authorized to log in as a service professional. Please login through the appropriate page."}, 401
    
    service_professional = ServiceProfessionals.query.filter_by(user_id=user.user_id).first()
    # Check if the service professional is verified
    if service_professional.is_verified == 0:
        return {"message": "Your account is not verified. Please contact support for verification."}, 401
    
    #Check if the service professional is blocked
    if user.status != 'active':
        return {"message" : "You have blocked by the admin, Kindly contact the Admin."}
    
    # If login is successful
    token = create_access_token(identity=str(user.user_id), additional_claims={"type" : "service_professional", "id": user.user_id})
    return {"access_token" : token, "username": user.username, "user_id": user.user_id, "role": user.role}, 200

@app.route('/professional_dashboard', methods=['GET'])
@jwt_required()
@cache.memoize(timeout=50)
def professional_dashboard_data():
    try:
       # Get user ID from JWT
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Invalid token"}), 401

        # Get the professional's profile using the user_id
        professional = ServiceProfessionals.query.filter_by(user_id=user_id).first()
        if not professional:
            return jsonify({"error": "Professional not found"}), 404
        
        # Get the total number of customers the professional has served (distinct customer IDs)
        total_customers = db.session.query(ServiceRequests.customer_id).filter(
            ServiceRequests.professional_id == professional.professional_id).distinct().count()

        # Get the total number of service requests received, closed, and rejected for the professional
        total_requests_received = db.session.query(ServiceRequests).filter(
            ServiceRequests.professional_id == professional.professional_id,
            ServiceRequests.service_status == 'requested').count()
        
        total_requests_closed = db.session.query(ServiceRequests).filter(
            ServiceRequests.professional_id == professional.professional_id,
            ServiceRequests.service_status == 'closed').count()

        total_requests_rejected = db.session.query(ServiceRequests).filter(
            ServiceRequests.professional_id == professional.professional_id,
            ServiceRequests.service_status == 'rejected').count()

        # Send the response with the gathered data
        return jsonify({
            "total_customers": total_customers,
            "total_requests_received": total_requests_received,
            "total_requests_closed": total_requests_closed,
            "total_requests_rejected": total_requests_rejected,
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/get_service_types', methods=['GET'])
def get_service_types():
    try:
        # Query all services
        services = Services.query.all()
        # Convert the query result into a list of dictionaries
        services_list = [{"id": service.service_id, "name": service.name} for service in services]
        return jsonify(services_list), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# View all service requests for a service professional
@app.route('/service_professional/view_all_service_requests', methods=['GET'])
@jwt_required()
def view_all_service_requests():
    # Get the logged-in user's ID from the JWT token
    current_user_id = get_jwt_identity()
    
    # Ensure the logged-in user is a service professional
    current_user = Users.query.get(current_user_id)
    if current_user.role != "service_professional":
        return {"message": "You are not authorized to access this resource."}, 403

    # Fetch all service requests for the logged-in professional
    service_requests = ServiceRequests.query.filter_by(professional_id=current_user_id).all()
     

    if not service_requests:
        return {"message": "No service requests found."}, 404

    # Prepare the response data
    service_requests_data = []
    for service_request in service_requests:
        # Get customer details from the Users table
        customer = Users.query.get(service_request.customer_id)
        customer_name = customer.name if customer else "Unknown"

        # Add the relevant data for the response
        service_request_data = {
            "request_id": service_request.request_id,
            "customer_name": customer_name,
            "service": service_request.service.name,  
            "date_of_request": service_request.date_of_request.strftime('%Y-%m-%d'),
            "location": service_request.location,
            "service_status":service_request.service_status
        }
        
        service_requests_data.append(service_request_data)

    return {"service_requests": service_requests_data}, 200

@app.route('/service_professional/completed_requests', methods=['GET'])
@jwt_required()
def get_completed_requests():
    # Get the logged-in user's ID from the JWT token
    current_user_id = get_jwt_identity()

    # Ensure the logged-in user is a service professional
    current_user = Users.query.get(current_user_id)
    if current_user.role != "service_professional":
        return jsonify({"message": "You are not authorized to access this resource."}), 403

    # Fetch all completed service requests for the logged-in professional
    completed_requests = ServiceRequests.query.filter_by(
        professional_id=current_user_id, service_status='closed'
    ).all()

    if not completed_requests:
        return jsonify({"message": "No completed requests found."}), 404

    # Prepare the response data
    completed_requests_data = [
        {
            "id": request.request_id,
            "customerName": request.customer.name if request.customer else "Unknown",
            "service": request.service.name if request.service else "Unknown",
            "date": request.date_of_request.strftime('%Y-%m-%d') if request.date_of_request else "N/A",
            "completionDate": request.date_of_completion.strftime('%Y-%m-%d') if request.date_of_completion else "N/A",
            "location": request.location,
        }
        for request in completed_requests
    ]

    return jsonify({"completedRequests": completed_requests_data}), 200

# Accept or reject a service request for a service professional
@app.route('/service_professional/<int:request_id>/accept_or_reject', methods=['POST'])
@jwt_required()  
def accept_or_reject_service_request(request_id):
    # Get the logged-in user's ID from the JWT token
    current_user_id = get_jwt_identity()

    # Get the service request by ID
    service_request = ServiceRequests.query.filter_by(request_id=request_id).first()
   
    # If the service request does not exist
    if not service_request:
        return jsonify({"message": "Service request not found."}), 404
    
    professional = ServiceProfessionals.query.filter_by(professional_id=service_request.professional_id).first()
    
    # Ensure the logged-in user is the service professional associated with this request
    # if professional.user_id != current_user_id:
    #     return jsonify({"message": "You are not authorized to manage this service request."}), 403

    # Get the action (accept or reject) from the request payload
    data = request.get_json()
    action = data.get("action") 

    # Validate the action
    if action not in ['assigned', 'reject']:
        return jsonify({"message": "Invalid action. Must be 'assigned' or 'reject'."}), 400

    # Update the service request status based on the action
    if action == 'assigned':
        service_request.service_status = 'assigned'
    elif action == 'reject':
        service_request.service_status = 'rejected'

    # Commit the changes to the database
    db.session.commit()

    return jsonify({
        "message": f"Service request has been {action}ed successfully.",
        "service_request": service_request.to_dict()  
    }), 200

# Close a service request (only for completed requests)
@app.route('/service_professional/<int:request_id>/close', methods=['POST'])
@jwt_required() 
def close_service_request(request_id):
    # Get the logged-in user's ID from the JWT token
    current_user_id = get_jwt_identity()

    # Get the service request by ID
    service_request = ServiceRequests.query.filter_by(request_id=request_id).first()

    # If the service request does not exist
    if not service_request:
        return jsonify({"message": "Service request not found."}), 404

    # # Ensure the logged-in user is the service professional assigned to this request
    # if service_request.professional_id != current_user_id:
    #     return jsonify({"message": "You are not authorized to close this service request."}), 403

    # Check if the service request status is already closed
    if service_request.service_status == 'closed':
        return jsonify({"message": "This service request is already closed."}), 400

    # # Ensure that the service request is marked as "completed" before closing
    # if service_request.service_status != 'completed':
    #     return jsonify({"message": "You can only close a service request that is marked as 'completed'."}), 400

    # Change the service request status to 'closed'
    service_request.service_status = 'closed'
    service_request.date_of_completion = datetime.utcnow()

    # Commit the changes to the database
    db.session.commit()

    return jsonify({
        "message": "Service request has been closed successfully.",
        "service_request": service_request.to_dict()  # Assuming you have a to_dict method
    }), 200
   
@app.route('/professional/search', methods=['GET'])
@jwt_required()  
def professional_search():
    try:
        # # Ensure the authenticated user is a service professional
        # current_user = get_jwt_identity()  
        
        # if current_user['role'] != 'Service Professional':
        #     return jsonify({"error": "You must be a service professional to perform this action"}), 403
        
        # Get search parameters from request
        query = request.args.get('q', '', type=str)  # Search query
        location = request.args.get('location', '', type=str)  # Location filter
        name = request.args.get('name', '', type=str)  # Name filter
        
        if not query and not location and not name:
            return jsonify({"error": "At least one search parameter is required"}), 400

        # Initialize results dictionary
        results = {'customers': []}

        # Start with Customers search based on the query
        customers = Users.query.filter(Users.role == 'Customer')  # Ensure we're only querying customers
        
        if query:
            # Filter customers by username or email if query is provided
            customers = customers.filter(
                (Users.username.ilike(f'%{query}%')) | 
                (Users.email.ilike(f'%{query}%'))
            )

        if location:
            # If location is provided, filter by location (assuming 'location' is a field in Users table)
            customers = customers.filter(Users.location.ilike(f'%{location}%'))

        if name:
            # If name is provided, filter by name (assuming 'name' is part of the user or profile table)
            customers = customers.filter(Users.username.ilike(f'%{name}%'))

        # Fetch the results
        customers = customers.all()
        
        # If no customers match the search criteria
        for customer in customers:
            results['customers'].append({
                "id": customer.user_id,
                "username": customer.username,
                "email": customer.email,
                "status": customer.status,
                "date_created": customer.date_created,
                "location": customer.location  # Assuming you have location field in Users model
            })

        # If no results are found
        if not results['customers']:
            return jsonify({"message": f"No customers found for the search criteria"}), 404

        # Return the results
        return jsonify({"results": results})

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "An error occurred during the search process"}), 500

@app.route('/professional/profile', methods=['GET'])
@jwt_required()
def get_professional_profile():
    try:
        current_user = get_jwt_identity()  # Get the current authenticated user
        professional = ServiceProfessionals.query.filter_by(user_id=current_user['user_id']).first()
        if not professional:
            return jsonify({"error": "Professional not found"}), 404

        return jsonify({
            "professional": {
                "id": professional.professional_id,
                "username": professional.user.username,
                "email": professional.user.email,
                "specialization": professional.specialization,
                "location": professional.location
            }
        })
    except Exception as e:
        return jsonify({"error": "An error occurred while fetching the profile"}), 500

@app.route('/professional/profile', methods=['PUT'])
@jwt_required()
def update_professional_profile():
    try:
        current_user = get_jwt_identity()  # Get the current authenticated user
        data = request.get_json()  # Get the new data from the request

        professional = ServiceProfessionals.query.filter_by(user_id=current_user['user_id']).first()
        if not professional:
            return jsonify({"error": "Professional not found"}), 404

        # Update the professional's profile fields
        professional.user.username = data.get('username', professional.user.username)
        professional.user.email = data.get('email', professional.user.email)
        professional.specialization = data.get('specialization', professional.specialization)
        professional.location = data.get('location', professional.location)

        db.session.commit()

        return jsonify({"message": "Profile updated successfully"})
    except Exception as e:
        return jsonify({"error": "An error occurred while updating the profile"}), 500



@app.route('/service_requests_status', methods=['GET'])
@jwt_required()
def service_requests_status():
    # Fetch counts for each service request status
    requested_count = ServiceRequests.query.filter_by(service_status='request').count() or 0
    closed_count = ServiceRequests.query.filter_by(service_status='closed').count() or 0
    rejected_count = ServiceRequests.query.filter_by(service_status='rejected').count() or 0
    received_count = ServiceRequests.query.filter_by(service_status='assigned').count() or 0

    # Create a dictionary for status counts
    status_counts = {
        'Requested': requested_count,
        'Closed': closed_count,
        'Rejected': rejected_count,
        'Received': received_count
    }

    # Debug: Print counts
    print("Status Counts:", status_counts)

    # Sanitize data
    status_counts = {
        key: int(value) if value is not None and not pd.isna(value) else 0
        for key, value in status_counts.items()
    }

    # Prevent empty pie chart
    if sum(status_counts.values()) == 0:
        return jsonify({"error": "No data available to plot."})

    # Create a pie chart
    plt.pie(
        status_counts.values(),
        labels=status_counts.keys(),
        autopct='%1.1f%%',
        startangle=90,
        colors=['#FFEB3B', '#4CAF50', '#F44336', '#FFEB4B']
    )
    plt.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle
    plt.title('Service Requests Status Distribution')

    # Save the plot to a BytesIO object
    img_bytes_io = BytesIO()
    plt.savefig(img_bytes_io, format='png')
    img_bytes_io.seek(0)

    # Encode the image as a base64 string
    img_base64 = base64.b64encode(img_bytes_io.getvalue()).decode('utf-8')

    # Close the figure to free up resources
    plt.close()

    return jsonify({"image": img_base64})



@app.route('/reviews_distribution', methods=['GET'])
@jwt_required()
def reviews_distribution():
    # Fetch all reviews and count the ratings distribution (assuming the 'rating' field in the 'Reviews' table)
    rating_counts = [0, 0, 0, 0, 0]  # For 1 to 5 stars
    
    reviews = Reviews.query.all()
    
    for review in reviews:
        if 1 <= review.rating <= 5:
            rating_counts[review.rating - 1] += 1
    
    # Create a bar chart for reviews distribution
    labels = ['1 Star', '2 Stars', '3 Stars', '4 Stars', '5 Stars']
    colors = plt.cm.Paired(np.linspace(0, 1, len(rating_counts)))

    plt.bar(labels, rating_counts, color=colors)
    plt.xlabel('Rating')
    plt.ylabel('Number of Reviews')
    plt.title('Reviews Distribution')

    # Save the plot to a BytesIO object
    img_bytes_io = BytesIO()
    plt.savefig(img_bytes_io, format='png')
    img_bytes_io.seek(0)

    # Encode the image as a base64 string
    img_base64 = base64.b64encode(img_bytes_io.getvalue()).decode('utf-8')

    # Close the figure to free up resources
    plt.close()

    return jsonify({"image": img_base64})

#--------------------------------------------------------------------------------------------------------------
#                                        ADMIN CONTROLLER PART
#--------------------------------------------------------------------------------------------------------------
@app.route('/admin_login', methods=['POST'])
def admin_login():
    # Handling the form submission
    data = request.get_json()
    username = data["username"]
    password = data["password"]
    user = Users.query.filter_by(username=username).first()
    
    # If the username or password is empty
    if username == '' or password == '':
        return {"message":"Please fill all the fields and try again"}, 400

    # If the username doesn't exist
    if not user:
        return {"message" : "Please check your Username and try again."}, 400

    # If the username exists, check the password
    if not user.check_password(password):
        return {"message" : "Please check your Password and try again."}, 400
    
    # If the user is not an admin
    if user.role != 'admin':
        return {"message" : "You are not authorized to log in as an admin."}, 401
    
    # If login is successful
    token = create_access_token(identity=str(user.user_id),additional_claims={"type" : "admin", "id" : user.user_id})
    return {"access_token" : token, "username": user.username, "user_id": user.user_id, "role": user.role}, 200

@app.route('/admin_dashboard', methods=['GET'])
@jwt_required()
@cache.memoize(timeout=50)
def admin_dashboard():
    try:
        # Get user ID from JWT
        user_id = get_jwt_identity()
        if not user_id:
            return jsonify({"error": "Invalid token"}), 401
        user = Users.query.filter_by(username='admin').one()


        # Count statistics
        total_customers = Users.query.filter(Users.role == 'customer').count()
        total_service_professionals = Users.query.filter(
        Users.role == 'service_professional', 
        ServiceProfessionals.is_verified == True
    ).join(ServiceProfessionals, ServiceProfessionals.user_id == Users.user_id).count()
        total_services = Services.query.count()
        blocked_users = Users.query.filter(Users.status == 'blocked').count()
        # List top-rated service professionals based on average reviews
        top_rated_professionals = (
            db.session.query(
                ServiceProfessionals,
                func.round(func.avg(Reviews.rating), 2).label('average_rating')
            )
            .join(Reviews, ServiceProfessionals.professional_id == Reviews.professional_id)
            .group_by(ServiceProfessionals.professional_id)
            .order_by(func.avg(Reviews.rating).desc())
            .limit(10)
            .all()
        )

        # Serialize the top-rated professionals data
        top_rated_professionals_data = [
            {
                "professional_id": professional.professional_id,
                "name": professional.user.username,
                "average_rating": rating,
                "service_type": professional.service_type,
                "description": professional.description
            }
            for professional, rating in top_rated_professionals
        ]

        # Prepare response data
        response = {
            "admin_user": {"id":user.user_id, "username": user.username},
            "total_customers": total_customers,
            "total_service_professionals": total_service_professionals,
            "total_services": total_services,
            "blocked_users": blocked_users,
            "top_rated_service_professionals": top_rated_professionals_data,
            "message": "Welcome to the admin dashboard!"
        }

        return jsonify(response), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/services', methods=['GET'])
@jwt_required()
def get_services():
    try:
        # Retrieve all services from the database
        services = Services.query.all()

        # If no services are found, return an appropriate message
        if not services:
            return {
                "message": "No services found.",
                "services": []
            }, 200

        # Format and return the list of services
        return {
            "message": "Services retrieved successfully.",
            "services": [
                {
                    "service_id": service.service_id,
                    "name": service.name,
                    "description": service.description,
                    "base_price": service.base_price,
                    "time_required": service.time_required
                }
                for service in services
            ]
        }, 200

    except Exception as e:
        # Handle unexpected errors
        return {
            "message": f"An error occurred while retrieving services: {str(e)}"
        }, 500

@app.route('/professionals', methods=['GET'])
@jwt_required()
def get_professionals():
    try:
        # Perform a JOIN to get data from both Users and ServiceProfessionals tables
        professionals = db.session.query(
            Users.user_id,
            Users.name,
            Users.status,
            ServiceProfessionals.service_type,
            ServiceProfessionals.experience,
            ServiceProfessionals.contact_info,
            ServiceProfessionals.is_verified,
            ServiceProfessionals.description
        ).join(
            ServiceProfessionals, ServiceProfessionals.user_id == Users.user_id
        ).filter(
            Users.role == 'service_professional'  # Ensure that the user is a service professional
        ).all()

        # If no professionals are found, return an appropriate message
        if not professionals:
            return jsonify({
                "message": "No service professionals found.",
                "professionals": []
            }), 200

        # Format and return the list of professionals
        return jsonify({
            "message": "Service professionals retrieved successfully.",
            "professionals": [
                {
                    "professional_id": professional.user_id,  # using user_id as the professional_id
                    "name": professional.name,
                    "service_name": professional.service_type,
                    "experience": professional.experience,
                    "contact_info": professional.contact_info,
                    "is_verified": professional.is_verified,
                    "description": professional.description,
                    "status": professional.status
                }
                for professional in professionals
            ]
        }), 200

    except Exception as e:
        # Handle unexpected errors
        return jsonify({
            "message": f"An error occurred while retrieving service professionals: {str(e)}"
        }), 500
    
@app.route('/service_requests', methods=['GET'])
@jwt_required()
def get_service_requests():
    try:
        # Query service requests and join through Professionals to fetch Users' names
        service_requests = (
            db.session.query(
                ServiceRequests.service_id,
                ServiceRequests.date_of_request,
                ServiceRequests.service_status,
                Users.name.label('professional_name')  
            )
            .outerjoin(ServiceProfessionals, ServiceRequests.professional_id == ServiceProfessionals.professional_id)
            .outerjoin(Users, ServiceProfessionals.user_id == Users.user_id)
            .all()
        )

        # Process the results correctly
        service_requests_data = [
            {
                'service_id': req.service_id,
                'assigned_professional': req.professional_name if req.professional_name else "Unassigned",
                'request_date': req.date_of_request.strftime('%Y-%m-%d'),
                'status': req.service_status,
            }
            for req in service_requests  
        ]

        return jsonify({'success': True, 'service_requests': service_requests_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/approve_service_professional/<int:user_id>', methods=['POST'])
@jwt_required()
def approve_service_professional(user_id):
    # Get the current logged-in user id from the JWT token
    current_user_id = get_jwt_identity()  
    # Fetch the user from the database using the user_id from JWT
    user = Users.query.get(current_user_id)
    
    # Ensure the current user is an admin
    if user.role != 'admin':
        return {"message": "You are not authorized to approve service professionals."}, 403

    # Fetch the service professional using the user_id passed in the URL
    service_professional = ServiceProfessionals.query.filter_by(user_id=user_id).first()

    # If the service professional doesn't exist
    if not service_professional:
        return {"message": "Service professional not found."}, 404

    # Check if the service professional is already verified
    if service_professional.is_verified:
        return {"message": "Service professional is already verified."}, 400

    # Approve the service professional by setting is_verified to True
    service_professional.is_verified = True

    try:
        db.session.commit()
        return {"message": "Service professional approved successfully."}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/reject_service_professional/<int:user_id>', methods=['POST'])
@jwt_required()
def reject_service_professional(user_id):
    # Get the current logged-in user id from the JWT token
    current_user_id = get_jwt_identity()  
    # Fetch the user from the database using the user_id from JWT
    user = Users.query.get(current_user_id)
    
    # Ensure the current user is an admin
    if user.role != 'admin':
        return {"message": "You are not authorized to reject service professionals."}, 403

    # Fetch the service professional using the user_id passed in the URL
    service_professional = ServiceProfessionals.query.filter_by(user_id=user_id).first()

    # If the service professional doesn't exist
    if not service_professional:
        return {"message": "Service professional not found."}, 404

    # Reject the service professional by setting is_verified to False
    service_professional.is_verified = False

    try:
        db.session.commit()
        return {"message": "Service professional rejected successfully."}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/delete_service_professional/<int:user_id>', methods=['POST'])
@jwt_required()
def delete_service_professional(user_id):
    # Get the current logged-in user id from the JWT token
    current_user_id = get_jwt_identity()  
    
    # Fetch the user from the database using the current_user_id
    user = Users.query.get(current_user_id)
    
    # Ensure the current user is an admin
    if user.role != 'admin':
        return {"message": "You are not authorized to delete service professionals."}, 403

    # Fetch the service professional using the user_id passed in the URL
    service_professional = ServiceProfessionals.query.filter_by(user_id=user_id).first()

    # If the service professional doesn't exist
    if not service_professional:
        return {"message": "Service professional not found."}, 404

    try:
        # First, delete the service professional record
        db.session.delete(service_professional)
        
        # Then, fetch and delete the corresponding user record from the Users table
        user_to_delete = Users.query.get(user_id)
        if user_to_delete:
            db.session.delete(user_to_delete)
        
        # Commit the changes to the database
        db.session.commit()
        
        return {"message": "Service professional and corresponding user deleted successfully."}, 200
    except Exception as e:
        # Rollback in case of any error
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/block_unblock_user/<int:user_id>', methods=['POST'])
@jwt_required()
def block_unblock_user(user_id):
    # Get the current logged-in user (admin)
    current_user_id = get_jwt_identity()

    # Fetch the admin user from the database
    admin_user = Users.query.get(current_user_id)

    # Ensure the current user is an admin
    if admin_user.role != 'admin':
        return {"message": "You are not authorized to block/unblock users."}, 403

    # Fetch the target user (customer or service professional) to be blocked/unblocked
    target_user = Users.query.get(user_id)
    
    if not target_user:
        return {"message": "Target user not found."}, 404

    # Block or Unblock the user based on status
    if target_user.status == 'active':
        target_user.status = 'blocked'
        action = 'blocked'
    else:
        target_user.status = 'active'
        action = 'unblocked'

    try:
        db.session.commit()
        return {"message": f"User successfully {action}."}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/add_service', methods=['POST'])
@jwt_required()
def add_service():
    # Get the current logged-in user
    current_user_id = get_jwt_identity()
    admin_user = Users.query.get(current_user_id)

    # Ensure the current user is an admin
    if not admin_user or admin_user.role != 'admin':
        return {"message": "You are not authorized to add services."}, 403

    # Get data from the request
    data = request.get_json()
    name = data.get("name")
    description = data.get("description")
    base_price = data.get("base_price")
    time_required = data.get("time_required")

    # Validate required fields
    if not name or not base_price or not time_required:
        return {"message": "Service name and base price and time_required are required."}, 400

    # Ensure base price is a valid positive number
    try:
        base_price = float(base_price)
        if base_price <= 0:
            raise ValueError
    except ValueError:
        return {"message": "Base price must be a positive number."}, 400

    # Create a new service entry
    new_service = Services(
        name=name,
        description=description,
        base_price=base_price,
        time_required=time_required
    )

    try:
        db.session.add(new_service)
        db.session.commit()
        return {
            "message": "Service added successfully.",
            "service": {
                "id": new_service.service_id,
                "name": new_service.name,
                "description": new_service.description,
                "base_price": new_service.base_price,
                "time_required" : new_service.time_required
            },
        }, 201
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/update_service/<int:service_id>', methods=['PUT'])
@jwt_required()
def update_service(service_id):
    # Get the current logged-in user
    current_user_id = get_jwt_identity()
    admin_user = Users.query.get(current_user_id)

    # Ensure the current user is an admin
    if not admin_user or admin_user.role != 'admin':
        return {"message": "You are not authorized to update services."}, 403

    # Fetch the service from the database
    service = Services.query.get(service_id)
    if not service:
        return {"message": "Service not found."}, 404

    # Get data from the request
    data = request.get_json()
    name = data.get("name")
    description = data.get("description")
    base_price = data.get("base_price")
    time_required = data.get("time_required")

    # Validate base price if provided
    if base_price is not None:
        try:
            base_price = float(base_price)
            if base_price <= 0:
                raise ValueError
        except ValueError:
            return {"message": "Base price must be a positive number."}, 400

    # Update service fields if new values are provided
    if name:
        service.name = name
    if description:
        service.description = description
    if base_price is not None:
        service.base_price = base_price
    if time_required:
        service.time_required = time_required

    try:
        db.session.commit()
        return {
            "message": "Service updated successfully.",
            "service": {
                "id": service.service_id,
                "name": service.name,
                "description": service.description,
                "base_price": service.base_price,
                "time_required": service.time_required
            },
        }, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred: {str(e)}"}, 500

@app.route('/delete_service/<int:service_id>', methods=['POST'])
@jwt_required()
def delete_service(service_id):
    # Get the current logged-in user
    current_user_id = get_jwt_identity()
    admin_user = Users.query.get(current_user_id)

    # Ensure the current user is an admin
    if not admin_user or admin_user.role != 'admin':
        return {"message": "You are not authorized to delete services."}, 403

    # Fetch the service from the database
    service = Services.query.get(service_id)
    if not service:
        return {"message": "Service not found."}, 404

    try:
        # Delete the service from the database
        db.session.delete(service)
        db.session.commit()
        return {"message": f"Service with ID {service_id} deleted successfully."}, 200
    except Exception as e:
        db.session.rollback()
        return {"message": f"An error occurred while deleting the service: {str(e)}"}, 500

@app.route('/admin/search', methods=['GET'])
@jwt_required()  
def admin_search():
    try:
        query = request.args.get('q', '', type=str)  # Get search query from request parameters
        
        if not query:
            return jsonify({"error": "Search query is missing"}), 400
        
        # Initialize results dictionary
        results = {
            'services': [],
            'customers': [],
            'professionals': []
        }

        # Search in Services
        services = Services.query.filter(Services.name.ilike(f'%{query}%')).all()
        for service in services:
            results['services'].append({
                "id": service.service_id,
                "name": service.name,
                "description": service.description,
                "base_price": service.base_price,
                "time_required": service.time_required
            })

        # Search in Customers
        customers = Users.query.filter(Users.username.ilike(f'%{query}%') | Users.email.ilike(f'%{query}%')).all()
        for customer in customers:
            results['customers'].append({
                "id": customer.user_id,
                "username": customer.username,
                "email": customer.email,
                "status": customer.status,
                "date_created": customer.date_created,
                "role": customer.role
            })

        # Search in Service Professionals
        professionals = db.session.query(ServiceProfessionals).join(Users).filter(
        (Users.username.ilike(f'%{query}%')) | (Users.email.ilike(f'%{query}%'))
        ).all()
        for professional in professionals:
            results['professionals'].append({
                "id": professional.professional_id,
                "username": professional.user.username,
                "email": professional.user.email,
                "specialization": professional.service_type
            })

        # If no results are found
        if not any(results.values()):
            return jsonify({"message": f"No results found for '{query}'"}), 404

        # Return the results
        return jsonify({"results": results})

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": "An error occurred during the search process"}), 500

@app.route('/service_statistics', methods=['GET'])
@jwt_required()
def service_statistics():
    # Fetch all services and their associated requests
    services = Services.query.all()
    
    # Initialize a dictionary to hold the count of requests for each service
    service_request_counts = {}

    # Loop over each service and count the number of requests
    for service in services:
        request_count = ServiceRequests.query.filter_by(service_id=service.service_id).count()
        service_request_counts[service.name] = request_count

    # List of colors (you can add more colors or choose a color palette)
    colors = plt.cm.Paired(np.linspace(0, 1, len(service_request_counts)))

    # Create a bar chart for service requests with different colors for each bar
    plt.bar(service_request_counts.keys(), service_request_counts.values(), color=colors)
    plt.xlabel('Service Categories')
    plt.ylabel('Number of Requests')
    plt.title('Service Statistics by Number of Requests')

    # Save the plot to a BytesIO object
    img_bytes_io = BytesIO()
    plt.savefig(img_bytes_io, format='png')
    img_bytes_io.seek(0)

    # Encode the image as a base64 string
    img_base64 = base64.b64encode(img_bytes_io.getvalue()).decode('utf-8')

    # Close the figure to free up resources
    plt.close()

    return jsonify({"image": img_base64})

@app.route('/user_distribution', methods=['GET'])
@jwt_required()
def user_distribution():
    # Fetch all customers and verified service professionals
    customers = Users.query.filter(Users.role == 'customer').all()
    verified_professionals = Users.query.join(ServiceProfessionals).filter(
        ServiceProfessionals.is_verified == True, 
        Users.role == 'service_professional'
    ).all()

    # Count customers and verified service professionals
    role_counts = {
        'customer': len(customers),
        'service_professional': len(verified_professionals)
    }

    # Create a pie chart
    plt.pie(role_counts.values(), labels=role_counts.keys(), autopct='%1.1f%%', startangle=90,
            colors=['#36a2eb', '#ff6384'])
    plt.axis('equal')
    plt.title('User Role Distribution')

    # Save the plot to a BytesIO object
    img_bytes_io = BytesIO()
    plt.savefig(img_bytes_io, format='png')
    img_bytes_io.seek(0)

    # Encode the image as a base64 string
    img_base64 = base64.b64encode(img_bytes_io.getvalue()).decode('utf-8')

    # Close the figure to free up resources
    plt.close()

    return jsonify({"image": img_base64})

# @app.route('/admin/export', methods=['GET'])
# @jwt_required()
# def export_csv():
#     # Get the current user from JWT
#     current_user_id = get_jwt_identity()
    
#     # Fetch user details to check if the current user is an admin
#     user = Users.query.filter_by(id=current_user_id).first()

#     # Check if the user is an admin
#     if user is None or user.role != 'admin':
#         return jsonify({"message": "You do not have permission to access this page."}), 403

#     # Trigger the Celery task to export the data
#     export_service_requests.apply_async()

#     # Return a JSON response indicating success
#     return jsonify({"message": "The export task has been triggered. You will be notified when it is complete."}), 200