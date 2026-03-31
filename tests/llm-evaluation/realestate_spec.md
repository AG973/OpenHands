# Real Estate Marketplace — Full Application Specification

## Overview
Build a complete, production-grade global real estate marketplace backend using FastAPI and SQLAlchemy.

## Required Database Models (10 tables)

### 1. User
- id, email (unique), hashed_password, first_name, last_name, phone, role (buyer/seller/agent/admin), is_active, created_at, updated_at

### 2. Property
- id, title, description, property_type (house/apartment/condo/townhouse/land/commercial), status (for_sale/for_rent/sold/rented/pending), price, price_per_sqft, bedrooms, bathrooms, square_feet, lot_size, year_built, address_id (FK), owner_id (FK→User), agent_id (FK→AgentProfile), agency_id (FK→Agency), is_featured, is_published, view_count, created_at, updated_at

### 3. Address
- id, street, city, state, zip_code, country, latitude, longitude, created_at

### 4. PropertyImage
- id, property_id (FK→Property), image_url, caption, is_primary, display_order, created_at

### 5. PropertyFeature
- id, property_id (FK→Property), feature_name, feature_value, created_at

### 6. Favorite
- id, user_id (FK→User), property_id (FK→Property), created_at

### 7. Inquiry
- id, buyer_id (FK→User), property_id (FK→Property), message, status (pending/responded/closed), response, responded_at, created_at

### 8. Review
- id, property_id (FK→Property), reviewer_id (FK→User), rating (1-5), comment, is_verified, created_at

### 9. Agency
- id, name, description, logo_url, website, phone, email, address, is_verified, created_at

### 10. AgentProfile
- id, user_id (FK→User, unique), agency_id (FK→Agency), license_number, bio, years_experience, specialization, is_verified, rating_average, total_reviews, created_at

## Required Files

1. **backend/models.py** — All 10 SQLAlchemy models with proper relationships, foreign keys, cascade deletes
2. **backend/main.py** — FastAPI application with CRUD endpoints for all models
3. **backend/auth.py** — JWT authentication with role-based access control (RBAC)
4. **backend/schemas.py** — Pydantic v2 schemas (BaseModel + ConfigDict) for all models
5. **requirements.txt** — All Python dependencies

## Quality Requirements
- All relationships and foreign keys properly defined
- SQLAlchemy ORM patterns (declarative_base, relationship, back_populates)
- created_at/updated_at timestamps on all models
- Pydantic v2 with ConfigDict(from_attributes=True)
- Proper enum types for roles, property types, statuses
- Cascade deletes where appropriate
- Input validation on schemas
