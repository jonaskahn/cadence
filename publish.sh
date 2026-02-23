h#!/bin/bash

# Cadence AI PyPI Deployment Script
# This script handles building and deploying the Cadence AI package to PyPI
# Automatically renames project to "cadence-py" to avoid PyPI conflicts

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project name constants
ORIGINAL_NAME="cadence"
PYPI_NAME="cadence-py"

# Print functions
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get current version from pyproject.toml
get_current_version() {
    grep '^version = ' pyproject.toml | cut -d'"' -f2
}

# Rename project for PyPI deployment
rename_for_pypi() {
    print_info "Renaming project from '$ORIGINAL_NAME' to '$PYPI_NAME' for PyPI deployment..."
    
    # Replace project name directly in pyproject.toml
    sed -i.bak "s/^name = \"$ORIGINAL_NAME\"/name = \"$PYPI_NAME\"/" pyproject.toml
    rm pyproject.toml.bak
    
    print_success "Project renamed to '$PYPI_NAME'"
}

# Restore original project name
restore_original_name() {
    print_info "Restoring original project name '$ORIGINAL_NAME'..."
    
    # Restore original name directly in pyproject.toml
    sed -i.bak "s/^name = \"$PYPI_NAME\"/name = \"$ORIGINAL_NAME\"/" pyproject.toml
    rm pyproject.toml.bak
    
    print_success "Project name restored to '$ORIGINAL_NAME'"
}

# Calculate next versions
calculate_next_versions() {
    local current_version=$1
    local major minor patch
    
    IFS='.' read -r major minor patch <<< "$current_version"
    
    local next_patch="$major.$minor.$((patch + 1))"
    local next_minor="$major.$((minor + 1)).0"
    local next_major="$((major + 1)).0.0"
    
    echo "$next_patch $next_minor $next_major"
}

# Update version in pyproject.toml
update_version() {
    local new_version=$1
    sed -i.bak "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
    rm pyproject.toml.bak
}

# Create git tag
create_git_tag() {
    local version=$1
    git add pyproject.toml
    git commit -m "Bump version to $version"
    git tag -a "v$version" -m "Release version $version"
    git push origin main
    git push origin "v$version"
}

# Build package using poetry
build_package() {
    print_info "Building $PYPI_NAME package using Poetry..."
    
    # Clean previous builds
    rm -rf dist/ build/ *.egg-info/
    
    # Build package using poetry
    poetry build
    
    print_success "Package built successfully"
}

# Upload to PyPI
upload_to_pypi() {
    local test_pypi=$1
    
    if [ "$test_pypi" = true ]; then
        print_info "Uploading $PYPI_NAME to TestPyPI..."
        poetry run python -m twine upload --repository testpypi dist/*
        print_success "Package uploaded to TestPyPI successfully"
        print_info "You can test the package with: pip install --index-url https://test.pypi.org/simple/ $PYPI_NAME"
    else
        print_info "Uploading $PYPI_NAME to PyPI..."
        poetry run python -m twine upload dist/*
        print_success "Package uploaded to PyPI successfully"
        print_info "You can install the package with: pip install $PYPI_NAME"
    fi
}

# Show help
show_help() {
    echo
    echo "Cadence AI PyPI Deployment Script"
    echo "Automatically renames project to '$PYPI_NAME' for PyPI deployment"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -v, --version       Show current version"
    echo "  --test              Upload to TestPyPI instead of PyPI"
    echo ""
    echo "Examples:"
    echo "  $0                  # Interactive deployment"
    echo "  $0 --test           # Deploy to TestPyPI"
    echo ""
    echo "Note: Project will be temporarily renamed to '$PYPI_NAME' during deployment"
    echo "      and restored to '$ORIGINAL_NAME' after completion."
    echo ""
}

# Check dependencies
check_dependencies() {
    print_info "Checking deployment dependencies..."
    
    # Check if poetry is available
    if ! command -v poetry &> /dev/null; then
        print_error "Poetry is not installed or not in PATH"
        print_info "Please install Poetry: https://python-poetry.org/docs/#installation"
        exit 1
    fi
    
    # Check if twine is available in poetry environment
    if ! poetry run python -c "import twine" &> /dev/null; then
        print_warning "Twine not found in poetry environment, installing..."
        poetry add --group dev twine
    fi
    
    print_success "All dependencies are available"
}

# Main deployment function
deploy() {
    local test_pypi=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --test)
                test_pypi=true
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            -v|--version)
                echo "Current version: $(get_current_version)"
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    # Check dependencies first
    check_dependencies
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    
    # Check if working directory is clean
    if [ -n "$(git status --porcelain)" ]; then
        print_warning "You have uncommitted changes. Consider committing them before deployment."
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Deployment cancelled."
            exit 0
        fi
    fi
    
    # Get current version
    local current_version=$(get_current_version)
    print_info "Current version: $current_version"
    
    # Calculate next versions
    read -r next_patch next_minor next_major <<< "$(calculate_next_versions "$current_version")"
    
    # Ask for version bump type
    echo
    echo "Select version bump type:"
    echo "1) patch ($current_version -> $next_patch)"
    echo "2) minor ($current_version -> $next_minor)"
    echo "3) major ($current_version -> $next_major)"
    echo "4) Skip version bump"
    read -p "Enter choice (1-4): " -n 1 -r
    echo
    
    local new_version="$current_version"
    case $REPLY in
        1)
            print_info "Bumping patch version..."
            new_version="$next_patch"
            update_version "$new_version"
            ;;
        2)
            print_info "Bumping minor version..."
            new_version="$next_minor"
            update_version "$new_version"
            ;;
        3)
            print_info "Bumping major version..."
            new_version="$next_major"
            update_version "$new_version"
            ;;
        4)
            print_info "Skipping version bump..."
            ;;
        *)
            print_error "Invalid choice. Exiting."
            exit 1
            ;;
    esac
    
    print_info "Version: $new_version"
    
    # Rename project for PyPI deployment
    rename_for_pypi
    
    # Build package
    build_package
    
    # Check if build was successful
    if [ ! -d "dist" ] || [ -z "$(ls -A dist/)" ]; then
        print_error "Build failed. No distribution files found."
        restore_original_name
        exit 1
    fi
    
    # Show what will be uploaded
    echo
    print_info "Files to be uploaded:"
    ls -la dist/
    
    # Ask for confirmation
    echo
    read -p "Deploy to PyPI? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled."
        restore_original_name
        exit 0
    fi
    
    # Upload to PyPI
    upload_to_pypi "$test_pypi"
    
    # Restore original project name
    restore_original_name
    
    # Optional: Create git tag
    read -p "Create git tag for version $new_version? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_info "Creating git tag..."
        create_git_tag "$new_version"
        print_success "Git tag v$new_version created!"
        print_warning "Don't forget to push the tag: git push origin v$new_version"
    fi
    
    # Show success message
    echo
    if [ "$test_pypi" = true ]; then
        print_success "Cadence AI deployment completed successfully!"
        print_info "Package: $PYPI_NAME (TestPyPI)"
        print_info "TestPyPI URL: https://test.pypi.org/project/$PYPI_NAME/"
    else
        print_success "Cadence AI deployment completed successfully!"
        print_info "Package: $PYPI_NAME"
        print_info "PyPI URL: https://pypi.org/project/$PYPI_NAME/"
    fi
    print_info "Project name has been restored to '$ORIGINAL_NAME'"
}

# Run deployment
deploy "$@"
