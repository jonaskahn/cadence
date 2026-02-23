#!/bin/bash
# Cadence Development Environment Setup

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_error()   { echo -e "${RED}✗${NC} $1"; }
print_info()    { echo -e "${BLUE}ℹ${NC} $1"; }
print_warn()    { echo -e "${YELLOW}⚠${NC} $1"; }
print_header()  { echo -e "\n${CYAN}──── $1 ────${NC}\n"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve docker compose command (prefer v2 plugin, fall back to v1)
DOCKER_COMPOSE_CMD=""
resolve_docker_compose() {
    if docker compose version &>/dev/null 2>&1; then
        DOCKER_COMPOSE_CMD="docker compose"
    elif command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE_CMD="docker-compose"
    else
        print_error "Neither 'docker compose' nor 'docker-compose' found."
        print_info "Install Docker Desktop: https://docs.docker.com/get-docker/"
        exit 1
    fi
}

check_prerequisites() {
    print_header "Checking Prerequisites"

    if command -v docker &>/dev/null; then
        print_success "Docker: $(docker --version)"
    else
        print_error "Docker is not installed."
        print_info "Install Docker Desktop: https://docs.docker.com/get-docker/"
        exit 1
    fi

    resolve_docker_compose
    print_success "Docker Compose: $DOCKER_COMPOSE_CMD"

    if command -v poetry &>/dev/null; then
        print_success "Poetry: $(poetry --version)"
    else
        print_error "Poetry is not installed."
        print_info "Install with: curl -sSL https://install.python-poetry.org | python3 -"
        exit 1
    fi

    if command -v python3 &>/dev/null; then
        PY_VER=$(python3 --version | cut -d' ' -f2)
        print_success "Python: $PY_VER"
        MAJOR=$(echo "$PY_VER" | cut -d'.' -f1)
        MINOR=$(echo "$PY_VER" | cut -d'.' -f2)
        if [ "$MAJOR" -lt 3 ] || ([ "$MAJOR" -eq 3 ] && [ "$MINOR" -lt 13 ]); then
            print_warn "Python 3.13+ recommended (you have $PY_VER)"
        fi
    else
        print_error "Python 3 is not installed."
        exit 1
    fi
}

setup_env_file() {
    print_header "Environment Configuration"

    if [ -f "$PROJECT_ROOT/.env" ]; then
        print_warn ".env already exists"
        read -rp "  Overwrite with fresh defaults? (y/N): " reply
        if [[ ! $reply =~ ^[Yy]$ ]]; then
            print_info "Keeping existing .env"
            return
        fi
    fi

    if [ ! -f "$PROJECT_ROOT/.env.example" ]; then
        print_error ".env.example not found at project root"
        exit 1
    fi

    cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
    print_success "Copied .env.example → .env"

    # Inject a freshly-generated secret key
    SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n')
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|CADENCE_SECRET_KEY=.*|CADENCE_SECRET_KEY=$SECRET_KEY|" "$PROJECT_ROOT/.env"
    else
        sed -i "s|CADENCE_SECRET_KEY=.*|CADENCE_SECRET_KEY=$SECRET_KEY|" "$PROJECT_ROOT/.env"
    fi
    print_success "Generated secure secret key"
    print_warn "Review $PROJECT_ROOT/.env for any site-specific values"
}

start_databases() {
    print_header "Starting Development Databases"
    "$SCRIPT_DIR/docker.sh" start
}

install_dependencies() {
    print_header "Installing Python Dependencies"
    cd "$PROJECT_ROOT"
    poetry install
    print_success "Dependencies installed"
}

run_migrations() {
    print_header "Running Database Migrations"
    cd "$PROJECT_ROOT"
    poetry run alembic upgrade head
    print_success "Migrations applied"
}

display_next_steps() {
    print_header "Setup Complete"

    echo -e "${GREEN}Your Cadence development environment is ready!${NC}"
    echo ""
    echo "  Next steps:"
    echo ""
    echo "  1. Start the API server:"
    echo -e "     ${BLUE}make dev${NC}"
    echo ""
    echo "  2. Bootstrap an admin user (first run only):"
    echo -e "     ${BLUE}poetry run python scripts/bootstrap.py${NC}"
    echo ""
    echo "  3. Generate the OpenAPI schema:"
    echo -e "     ${BLUE}poetry run python scripts/generate_openapi.py${NC}"
    echo ""
    echo "  4. Manage Docker services:"
    echo -e "     ${BLUE}./scripts/docker.sh [start|stop|restart|status|logs|reset]${NC}"
    echo ""
    echo "  Service URLs:"
    echo "    API          http://localhost:8000"
    echo "    Swagger UI   http://localhost:8000/docs"
    echo "    pgAdmin      http://localhost:5050  (admin@cadence.local / admin)"
    echo "    Mongo Express http://localhost:8081  (admin / admin)"
    echo "    Redis Cmdr   http://localhost:8082  (admin / admin)"
    echo "    MinIO UI     http://localhost:9001  (cadence / cadence_dev_password)"
    echo ""
}

main() {
    echo ""
    echo -e "${GREEN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Cadence v2 — Development Setup      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════╝${NC}"
    echo ""

    check_prerequisites
    setup_env_file
    start_databases
    install_dependencies
    run_migrations
    display_next_steps

    echo -e "${GREEN}Done.${NC}"
    echo ""
}

main
