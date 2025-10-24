#!/usr/bin/env python3
"""
Migration script to add access control fields to reports table

Adds the following fields:
- generated_by: Tracks who/what created the report (user ID or 'bee-service')
- access_grants: JSON array of user_ids granted access to service-generated reports
- access_type: Enum to differentiate 'user-owned' vs 'service-generated' reports
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import db, init_app
from flask import Flask
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Add access control fields to reports table"""
    app = Flask(__name__)

    # Configure database
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/sting_app?sslmode=disable'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        db.init_app(app)

        try:
            with db.engine.connect() as conn:
                # Step 1: Create access_type enum if it doesn't exist
                logger.info("Creating report_access_type enum...")
                conn.execute("""
                    DO $$ BEGIN
                        CREATE TYPE report_access_type AS ENUM ('user-owned', 'service-generated');
                    EXCEPTION
                        WHEN duplicate_object THEN null;
                    END $$;
                """)
                conn.commit()

                # Step 2: Check and add generated_by column
                result = conn.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='reports' AND column_name='generated_by'
                """)

                if result.rowcount == 0:
                    logger.info("Adding generated_by column...")
                    conn.execute("""
                        ALTER TABLE reports
                        ADD COLUMN generated_by VARCHAR(255)
                    """)
                    conn.commit()

                    # Set default value for existing records (user-generated)
                    logger.info("Setting default generated_by values for existing reports...")
                    conn.execute("""
                        UPDATE reports
                        SET generated_by = user_id
                        WHERE generated_by IS NULL
                    """)
                    conn.commit()
                else:
                    logger.info("Column generated_by already exists, skipping...")

                # Step 3: Check and add access_grants column
                result = conn.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='reports' AND column_name='access_grants'
                """)

                if result.rowcount == 0:
                    logger.info("Adding access_grants column...")
                    conn.execute("""
                        ALTER TABLE reports
                        ADD COLUMN access_grants JSON DEFAULT '[]'
                    """)
                    conn.commit()
                else:
                    logger.info("Column access_grants already exists, skipping...")

                # Step 4: Check and add access_type column
                result = conn.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name='reports' AND column_name='access_type'
                """)

                if result.rowcount == 0:
                    logger.info("Adding access_type column...")
                    conn.execute("""
                        ALTER TABLE reports
                        ADD COLUMN access_type report_access_type DEFAULT 'user-owned'
                    """)
                    conn.commit()

                    # Set default value for existing records (all user-owned)
                    logger.info("Setting default access_type values for existing reports...")
                    conn.execute("""
                        UPDATE reports
                        SET access_type = 'user-owned'
                        WHERE access_type IS NULL
                    """)
                    conn.commit()
                else:
                    logger.info("Column access_type already exists, skipping...")

                # Step 5: Create index on generated_by for performance
                logger.info("Creating index on generated_by...")
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reports_generated_by
                    ON reports(generated_by)
                """)
                conn.commit()

                # Step 6: Create index on access_type for performance
                logger.info("Creating index on access_type...")
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reports_access_type
                    ON reports(access_type)
                """)
                conn.commit()

                logger.info("Migration completed successfully!")
                logger.info("Access control fields added to reports table:")
                logger.info("  - generated_by: Tracks report creator")
                logger.info("  - access_grants: Manages service-generated report access")
                logger.info("  - access_type: Differentiates user-owned vs service-generated")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise

def rollback_migration():
    """Rollback the migration (remove access control columns)"""
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL',
        'postgresql://postgres:postgres@localhost:5432/sting_app?sslmode=disable'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    with app.app_context():
        db.init_app(app)

        try:
            with db.engine.connect() as conn:
                logger.info("Rolling back access control fields migration...")

                # Drop indexes
                conn.execute("DROP INDEX IF EXISTS idx_reports_generated_by")
                conn.execute("DROP INDEX IF EXISTS idx_reports_access_type")

                # Drop columns
                conn.execute("ALTER TABLE reports DROP COLUMN IF EXISTS generated_by")
                conn.execute("ALTER TABLE reports DROP COLUMN IF EXISTS access_grants")
                conn.execute("ALTER TABLE reports DROP COLUMN IF EXISTS access_type")

                # Drop enum type
                conn.execute("DROP TYPE IF EXISTS report_access_type")

                conn.commit()
                logger.info("Rollback completed successfully!")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Add access control fields to reports table')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    if args.rollback:
        rollback_migration()
    else:
        run_migration()
