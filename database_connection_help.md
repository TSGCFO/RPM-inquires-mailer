# Database Connection Troubleshooting

## Issue: DNS Resolution Failure

The hostname `dpg-d0dtgaidbo4c739abnv0-a` cannot be resolved.

## Solution Options

### Option 1: Use Full Render Database URL

Render databases typically have full hostnames like:

```txt
PGHOST=dpg-d0dtgaidbo4c739abnv0-a.render.com
```

### Option 2: Get External Connection String

1. Go to your Render Dashboard
2. Navigate to your PostgreSQL database
3. Look for "External Database URL" or "Connection Info"
4. Copy the full hostname (should end with `.render.com`)

### Option 3: Use Complete Connection String

Instead of separate variables, you might need:

```bash
# Example format:
postgresql://user:password@hostname.render.com:5432/database
```

## Testing Database Connection

Try these commands to test connectivity:

```bash
# Test with .render.com suffix
ping dpg-d0dtgaidbo4c739abnv0-a.render.com

# Test direct PostgreSQL connection
psql postgresql://rpm_auto_user:x0nth4SNq4DqSzyRtI839S9IE5WE5TG6@dpg-d0dtgaidbo4c739abnv0-a.render.com:5432/rpm_auto
```

## Expected Render Database URL Format

Render databases typically look like:

- **Hostname**: `dpg-xxxxxxx-a.render.com`
- **Port**: `5432`
- **SSL**: Required (`sslmode=require`)

## Quick Fix

Update your `.env` file with the full hostname:

```bash
PGHOST=dpg-d0dtgaidbo4c739abnv0-a.render.com
PGHOST_2=dpg-d0dtgaidbo4c739abnv0-a.render.com
```
