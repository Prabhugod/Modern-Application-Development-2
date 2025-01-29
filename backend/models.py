# Importing the required libraries
from flask_sqlalchemy import SQLAlchemy
from app import app
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz


#Making variable for Indian Standard Time
IST = pytz.timezone('Asia/Kolkata')

# Creating the database object
db = SQLAlchemy(app)

# Creating the Models
# Users table to manage all types of users: Admin, Service Professional, Customer
class Users(db.Model):
    __tablename__ = 'users'
    user_id = db.Column(db.Integer, primary_key=True, nullable=False)
    username = db.Column(db.String(15), unique=True, nullable=False)
    passhash = db.Column(db.String(500), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(64), unique=True, nullable=False)
    role = db.Column(db.Enum('admin', 'service_professional', 'customer', name='user_roles') , default='customer' , nullable=False)
    date_created = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    status = db.Column(db.Enum('active', 'blocked', name='user_status'), default='active')
    location = db.Column(db.String(6), nullable=False)
    # Relationships
    professional_profile = db.relationship('ServiceProfessionals', back_populates='user', uselist=False)
    service_requests = db.relationship('ServiceRequests', back_populates='customer')
    reviews = db.relationship('Reviews', back_populates='customer')
    
    # Password hashing functions
    @property
    def password(self):
        raise AttributeError('Password is not a readable attribute.')

    @password.setter
    def password(self, password):
        self.passhash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.passhash, password)
    
    
    def to_dict(self):
        professional_profile_json = {
            'professional_id': self.professional_profile.professional_id,
            'service_type': self.professional_profile.service_type
        } if self.professional_profile else None

        service_requests_json = [{'request_id': service.request_id, 'service_status': service.service_status} 
                                    for service in self.service_requests] if self.service_requests else []

        reviews_json = [{'review_id': review.review_id, 'rating': review.rating} 
                        for review in self.reviews] if self.reviews else []

        return {
            'user_id': self.user_id,
            'username': self.username,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'date_created': self.date_created.isoformat() if self.date_created else None,
            'status': self.status,
            'professional_profile': professional_profile_json,
            'service_requests': service_requests_json,
            'reviews': reviews_json
        }

# Many-to-Many Relationship Between ServiceProfessionals and Services
service_professional_association = db.Table(
    'service_professional_association',
    db.Column('service_id', db.Integer, db.ForeignKey('services.service_id'), primary_key=True),
    db.Column('professional_id', db.Integer, db.ForeignKey('service_professionals.professional_id'), primary_key=True)
)

# Service Professionals table for additional professional details
class ServiceProfessionals(db.Model):
    __tablename__ = 'service_professionals'
    professional_id = db.Column(db.Integer, primary_key=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    experience = db.Column(db.Integer)  
    contact_info = db.Column(db.String(100), nullable=True)
    is_verified = db.Column(db.Boolean, default=False)
    description = db.Column(db.String(300), nullable=True)
    
    # Relationships
    user = db.relationship('Users', back_populates='professional_profile')
    service_requests = db.relationship('ServiceRequests', back_populates='professional')
    reviews = db.relationship('Reviews', back_populates='professional')
    services = db.relationship('Services', secondary=service_professional_association, back_populates='professionals')

    def to_dict(self):
        user_json = {
            'user_id': self.user.user_id,
            'username': self.user.username
        } if self.user else None

        service_requests_json = [{'request_id': req.request_id, 'service_status': req.service_status} 
                                for req in self.service_requests] if self.service_requests else []

        reviews_json = [{'review_id': review.review_id, 'rating': review.rating} 
                        for review in self.reviews] if self.reviews else []

        return {
            'professional_id': self.professional_id,
            'user_id': self.user_id,
            'service_type': self.service_type,
            'experience': self.experience,
            'contact_info': self.contact_info,
            'is_verified': self.is_verified,
            'description': self.description,
            'user': user_json,
            'service_requests': service_requests_json,
            'reviews': reviews_json
        }
 
# Services table to define service types and details
class Services(db.Model):
    __tablename__ = 'services'
    service_id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.String(50), unique=True, nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    time_required = db.Column(db.Integer, nullable=False)  # in minutes
    description = db.Column(db.String(200), nullable=True)

    # Relationships
    service_requests = db.relationship('ServiceRequests', back_populates='service')
    professionals = db.relationship('ServiceProfessionals', secondary=service_professional_association, back_populates='services')

    # Method to return service data as a dictionary
    def to_dict(self):
        service_requests_json = self.service.to_dict() if self.service else None
        for service in self.service_requests:
            service_requests_json = service.to_json()
            service_requests_json.append(service_requests_json)
        return {
            'service_id': self.service_id,
            'name': self.name,
            'base_price': self.base_price,
            'time_required': self.time_required,
            'description': self.description,
            'service_requests': service_requests_json
            }
    
# Service Requests table for managing customer service requests
class ServiceRequests(db.Model):
    __tablename__ = 'service_requests'
    request_id = db.Column(db.Integer, primary_key=True, nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('services.service_id'), nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('service_professionals.professional_id'), nullable=True)
    date_of_request = db.Column(db.DateTime, default=lambda: datetime.now(IST))
    date_of_completion = db.Column(db.DateTime, nullable=True)
    service_status = db.Column(db.Enum('requested', 'assigned', 'closed', 'rejected', name='service_status'), default='requested')
    remarks = db.Column(db.String(200), nullable=True)
    location = db.Column(db.Integer, nullable=True)

    # Relationships
    customer = db.relationship('Users', back_populates='service_requests')
    service = db.relationship('Services', back_populates='service_requests')
    professional = db.relationship('ServiceProfessionals', back_populates='service_requests')
    
    
    def to_dict(self):
        customer_json = {
            'user_id': self.customer.user_id,
            'username': self.customer.username
        } if self.customer else None

        service_json = {
            'service_id': self.service.service_id,
            'name': self.service.name
        } if self.service else None

        professional_json = {
            'professional_id': self.professional.professional_id,
            'service_type': self.professional.service_type
        } if self.professional else None

        return {
            'request_id': self.request_id,
            'service_id': self.service_id,
            'customer_id': self.customer_id,
            'professional_id': self.professional_id,
            'date_of_request': self.date_of_request.isoformat() if self.date_of_request else None,
            'date_of_completion': self.date_of_completion.isoformat() if self.date_of_completion else None,
            'service_status': self.service_status,
            'remarks': self.remarks,
            'location': self.location,
            'customer': customer_json,
            'service': service_json,
            'professional': professional_json
        }

# Reviews table to capture customer feedback on completed services
class Reviews(db.Model):
    __tablename__ = 'reviews'
    review_id = db.Column(db.Integer, primary_key=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    professional_id = db.Column(db.Integer, db.ForeignKey('service_professionals.professional_id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  
    review_text = db.Column(db.String(200), nullable=True)
    date_posted = db.Column(db.DateTime, default=lambda: datetime.now(IST))

    # Relationships
    customer = db.relationship('Users', back_populates='reviews')
    professional = db.relationship('ServiceProfessionals', back_populates='reviews')
    
    
    def to_dict(self):
        customer_json = {
            'user_id': self.customer.user_id,
            'username': self.customer.username
        } if self.customer else None

        professional_json = {
            'professional_id': self.professional.professional_id,
            'service_type': self.professional.service_type
        } if self.professional else None

        return {
            'review_id': self.review_id,
            'customer_id': self.customer_id,
            'professional_id': self.professional_id,
            'rating': self.rating,
            'review_text': self.review_text,
            'date_posted': self.date_posted.isoformat() if self.date_posted else None,
            'customer': customer_json,
            'professional': professional_json
        }

# Creating database if it doesn't exist
with app.app_context():
    db.create_all()

    # Create admin if admin doesn't exist
    admin = Users.query.filter_by(role='admin').first()
    if not admin:
        admin = Users(username='admin', password='admin', name='Admin', email='admin@admin.com', role='admin', location='000000')
        db.session.add(admin)
        db.session.commit()
