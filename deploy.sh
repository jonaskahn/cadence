#!/bin/bash

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

# Calculate next version
get_next_version() {
    local current_version=$1
    local bump_type=$2
    
    IFS='.' read -ra VERSION_PARTS <<< "$current_version"
    local major=${VERSION_PARTS[0]}
    local minor=${VERSION_PARTS[1]}
    local patch=${VERSION_PARTS[2]}
    
    case $bump_type in
        "patch")
            echo "$major.$minor.$((patch + 1))"
            ;;
        "minor")
            echo "$major.$((minor + 1)).0"
            ;;
        "major")
            echo "$((major + 1)).0.0"
            ;;
        *)
            echo "$current_version"
            ;;
    esac
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
    echo "  --patch             Bump patch version (0.1.0 -> 0.1.1)"
    echo "  --minor             Bump minor version (0.1.0 -> 0.2.0)"
    echo "  --major             Bump major version (0.1.0 -> 1.0.0)"
    echo "  --no-bump           Don't bump version"
    echo "  --no-tag            Don't create git tag"
    echo "  --test              Upload to TestPyPI instead of PyPI"
    echo ""
    echo "Examples:"
    echo "  $0 --patch          # Bump patch version and deploy"
    echo "  $0 --minor          # Bump minor version and deploy"
    echo "  $0 --no-bump        # Deploy current version without bumping"
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
    local bump_type=""
    local create_tag=true
    local test_pypi=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --patch)
                bump_type="patch"
                shift
                ;;
            --minor)
                bump_type="minor"
                shift
                ;;
            --major)
                bump_type="major"
                shift
                ;;
            --no-bump)
                bump_type=""
                shift
                ;;
            --no-tag)
                create_tag=false
                shift
                ;;
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
    if ! git diff-index --quiet HEAD --; then
        print_warning "Working directory is not clean. Please commit or stash your changes."
    fi
    
    # Get current version
    local current_version=$(get_current_version)
    print_info "Current version: $current_version"
    
    # Determine next version
    local next_version=""
    if [ -n "$bump_type" ]; then
        next_version=$(get_next_version "$current_version" "$bump_type")
        print_info "Next version will be: $next_version"
        
        # Confirm version bump
        echo
        echo "Select version bump type:"
        echo "1) patch ($current_version -> $next_version)"
        echo "2) minor ($current_version -> $next_version)"
        echo "3) major ($current_version -> $next_version)"
        echo "4) Skip version bump"
        echo
        read -p "Enter your choice (1-4): " choice
        
        case $choice in
            1|2|3)
                print_info "Proceeding with version bump to $next_version"
                update_version "$next_version"
                ;;
            4)
                print_info "Skipping version bump"
                bump_type=""
                next_version="$current_version"
                ;;
            *)
                print_error "Invalid choice"
                exit 1
                ;;
        esac
    else
        next_version="$current_version"
    fi
    
    # Rename project for PyPI deployment
    rename_for_pypi
    
    # Build package
    build_package
    
    # Upload to PyPI
    upload_to_pypi "$test_pypi"
    
    # Restore original project name
    restore_original_name
    
    # Create git tag if requested
    if [ "$create_tag" = true ] && [ -n "$bump_type" ]; then
        print_info "Creating git tag for version $next_version"
        create_git_tag "$next_version"
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
