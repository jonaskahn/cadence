#!/bin/bash
# Cadence Docker Compose Management
# Manages the local development database stack

set -euo pipefail

COMPOSE_FILE="devops/local/database.yaml"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
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

# Resolve docker compose command
docker_compose() {
    if docker compose version &>/dev/null 2>&1; then
        docker compose -f "$PROJECT_ROOT/$COMPOSE_FILE" "$@"
    elif command -v docker-compose &>/dev/null; then
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" "$@"
    else
        print_error "Neither 'docker compose' nor 'docker-compose' found. Install Docker Desktop or the Compose plugin."
        exit 1
    fi
}

cmd_start() {
    print_header "Starting Cadence Services"
    docker_compose up -d
    echo ""
    print_info "Waiting for health checks..."
    sleep 5
    docker_compose ps
    echo ""
    print_success "Services started"
    echo ""
    echo "  PostgreSQL   localhost:5432"
    echo "  MongoDB      localhost:27017"
    echo "  Redis        localhost:6379"
    echo "  MinIO API    localhost:9000"
    echo "  MinIO UI     http://localhost:9001"
    echo "  pgAdmin      http://localhost:5050"
    echo "  Mongo Express http://localhost:8081"
    echo "  Redis Cmdr   http://localhost:8082"
}

cmd_stop() {
    print_header "Stopping Cadence Services"
    docker_compose down
    print_success "Services stopped"
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    print_header "Service Status"
    docker_compose ps
}

cmd_logs() {
    local service="${1:-}"
    print_header "Service Logs${service:+ — $service}"
    if [ -n "$service" ]; then
        docker_compose logs -f "$service"
    else
        docker_compose logs -f
    fi
}

cmd_reset() {
    print_header "Reset — Remove All Data"
    print_warn "This will DELETE all database volumes and data permanently."
    echo ""
    read -rp "Type 'yes' to confirm: " confirm
    if [ "$confirm" != "yes" ]; then
        print_info "Aborted."
        exit 0
    fi
    docker_compose down -v
    print_success "All volumes removed. Run './scripts/docker.sh start' to start fresh."
}

usage() {
    echo ""
    echo -e "${CYAN}Cadence Docker Management${NC}"
    echo ""
    echo "Usage: ./scripts/docker.sh <command> [service]"
    echo ""
    echo "Commands:"
    echo -e "  ${GREEN}start${NC}           Start all services"
    echo -e "  ${GREEN}stop${NC}            Stop all services"
    echo -e "  ${GREEN}restart${NC}         Restart all services"
    echo -e "  ${GREEN}status${NC}          Show service status"
    echo -e "  ${GREEN}logs [service]${NC}  Tail logs (optionally filter to one service)"
    echo -e "  ${GREEN}reset${NC}           Stop and delete all volumes ${RED}(destructive)${NC}"
    echo ""
    echo "Services: postgres, mongo, redis, minio, pgadmin, mongo-express, redis-commander"
    echo ""
}

main() {
    local command="${1:-}"
    shift || true

    case "$command" in
        start)   cmd_start ;;
        stop)    cmd_stop ;;
        restart) cmd_restart ;;
        status|ps) cmd_status ;;
        logs)    cmd_logs "${1:-}" ;;
        reset)   cmd_reset ;;
        ""|--help|-h) usage ;;
        *)
            print_error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
