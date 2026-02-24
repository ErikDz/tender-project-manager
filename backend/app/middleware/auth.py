"""Supabase JWT authentication middleware."""

from functools import wraps
from flask import request, jsonify, g, current_app


def require_auth(f):
    """Decorator that verifies Supabase JWT and injects user context."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        supabase = current_app.supabase

        if not supabase:
            return jsonify({"error": "Supabase not configured"}), 500

        try:
            # Verify JWT and get user
            user_response = supabase.auth.get_user(token)
            user = user_response.user
            if not user:
                return jsonify({"error": "Invalid token"}), 401

            g.user_id = user.id
            g.token = token

            # Look up organization membership
            org_result = supabase.table("org_members") \
                .select("organization_id, role") \
                .eq("user_id", user.id) \
                .execute()

            if org_result.data:
                g.organization_id = org_result.data[0]["organization_id"]
                g.user_role = org_result.data[0]["role"]
            else:
                # Auto-create a personal organization for new users
                email = user.email or "User"
                org_name = email.split("@")[0] + "'s Organization"

                org = supabase.table("organizations") \
                    .insert({"name": org_name}) \
                    .execute()
                org_id = org.data[0]["id"]

                supabase.table("org_members").insert({
                    "organization_id": org_id,
                    "user_id": user.id,
                    "role": "admin",
                }).execute()

                g.organization_id = org_id
                g.user_role = "admin"

        except Exception as e:
            return jsonify({"error": f"Authentication failed: {str(e)}"}), 401

        return f(*args, **kwargs)
    return decorated
