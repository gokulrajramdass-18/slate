-- Create default admin user
-- Username: admin
-- Password: admin

-- Generate UUID for admin user
-- Using a fixed UUID for consistency: 00000000-0000-0000-0000-000000000001

INSERT OR IGNORE INTO users (
    id,
    username,
    email,
    password_hash,
    full_name,
    status,
    is_superadmin,
    created,
    updated,
    last_login
) VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    'admin@localhost',
    '$2b$12$492IqJ92IoDzTeXRuP3dHOg/VAZlvkszODp3QhZ0l3bMqDrTOiLFO',
    'System Administrator',
    'active',
    1,
    datetime('now'),
    datetime('now'),
    NULL
);

-- Get admin role ID
-- Assuming admin role exists from migration
-- Assign admin role to admin user

INSERT OR IGNORE INTO user_roles (
    id,
    user_id,
    role_id,
    assigned_by,
    assigned_at
)
SELECT
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000001',
    r.id,
    '00000000-0000-0000-0000-000000000001',
    datetime('now')
FROM roles r
WHERE r.name = 'admin';

SELECT 'Admin user created successfully!' as message;
SELECT * FROM users WHERE username = 'admin';
