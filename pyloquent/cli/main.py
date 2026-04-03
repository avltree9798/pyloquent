"""Main CLI entry point for Pyloquent."""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Optional

from pyloquent.cli.commands import (
    MakeMigrationCommand,
    MakeModelCommand,
    MigrateCommand,
    MigrateFreshCommand,
    MigrateRollbackCommand,
    MigrateStatusCommand,
)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="pyloquent",
        description="Pyloquent ORM CLI Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # make:migration command
    make_migration = subparsers.add_parser(
        "make:migration",
        help="Create a new migration file",
    )
    make_migration.add_argument("name", help="Migration name")
    make_migration.add_argument("--table", "-t", help="Table name for table-specific migrations")
    make_migration.add_argument("--create", "-c", action="store_true", help="Create a new table")
    make_migration.add_argument(
        "--path", "-p", default="migrations", help="Migrations directory path"
    )

    # make:model command
    make_model = subparsers.add_parser(
        "make:model",
        help="Create a new model file",
    )
    make_model.add_argument("name", help="Model name")
    make_model.add_argument("--table", "-t", help="Explicit table name")
    make_model.add_argument(
        "--migration", "-m", action="store_true", help="Create a migration for the model"
    )
    make_model.add_argument("--path", "-p", default="models", help="Models directory path")
    make_model.add_argument(
        "--migrations-path", default="migrations", help="Migrations directory path"
    )

    # migrate command
    migrate = subparsers.add_parser(
        "migrate",
        help="Run pending migrations",
    )
    migrate.add_argument("--path", "-p", default="migrations", help="Migrations directory path")
    migrate.add_argument("--config", help="Path to database configuration file")

    # migrate:rollback command
    migrate_rollback = subparsers.add_parser(
        "migrate:rollback",
        help="Rollback migrations",
    )
    migrate_rollback.add_argument(
        "--path", "-p", default="migrations", help="Migrations directory path"
    )
    migrate_rollback.add_argument(
        "--steps", "-s", type=int, default=1, help="Number of batches to rollback"
    )
    migrate_rollback.add_argument("--config", help="Path to database configuration file")

    # migrate:status command
    migrate_status = subparsers.add_parser(
        "migrate:status",
        help="Show migration status",
    )
    migrate_status.add_argument(
        "--path", "-p", default="migrations", help="Migrations directory path"
    )
    migrate_status.add_argument("--config", help="Path to database configuration file")

    # migrate:fresh command
    migrate_fresh = subparsers.add_parser(
        "migrate:fresh",
        help="Drop all tables and re-run migrations",
    )
    migrate_fresh.add_argument(
        "--path", "-p", default="migrations", help="Migrations directory path"
    )
    migrate_fresh.add_argument("--config", help="Path to database configuration file")

    return parser


async def run_command(args: argparse.Namespace) -> int:
    """Run the appropriate command based on parsed arguments.

    Args:
        args: Parsed arguments

    Returns:
        Exit code
    """
    if not args.command:
        print("No command specified. Use --help for usage.")
        return 1

    command = args.command

    try:
        if command == "make:migration":
            cmd = MakeMigrationCommand(
                migrations_path=args.path,
            )
            await cmd.handle(name=args.name, table=args.table, create=args.create)

        elif command == "make:model":
            cmd = MakeModelCommand(
                models_path=args.path,
                migrations_path=args.migrations_path,
            )
            await cmd.handle(
                name=args.name,
                table=args.table,
                create_migration=args.migration,
            )

        elif command == "migrate":
            cmd = MigrateCommand(
                migrations_path=args.path,
                config_path=args.config,
            )
            await cmd.handle()

        elif command == "migrate:rollback":
            cmd = MigrateRollbackCommand(
                migrations_path=args.path,
                config_path=args.config,
            )
            await cmd.handle(steps=args.steps)

        elif command == "migrate:status":
            cmd = MigrateStatusCommand(
                migrations_path=args.path,
                config_path=args.config,
            )
            await cmd.handle()

        elif command == "migrate:fresh":
            cmd = MigrateFreshCommand(
                migrations_path=args.path,
                config_path=args.config,
            )
            await cmd.handle()

        else:
            print(f"Unknown command: {command}")
            return 1

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def main(args: Optional[List[str]] = None) -> int:
    """Main entry point.

    Args:
        args: Command line arguments (defaults to sys.argv)

    Returns:
        Exit code
    """
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    return asyncio.run(run_command(parsed_args))


if __name__ == "__main__":
    sys.exit(main())
