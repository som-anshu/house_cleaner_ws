#!/usr/bin/env bash
# Automated test script to validate portability fixes
# Run from workspace root: ./test_portability.sh
#
# Tests:
# 1. No hardcoded absolute paths in tracked files
# 2. env.sh works dynamically (doesn't hardcode workspace path)
# 3. run_house_cleaner.sh uses dynamic path detection
# 4. run_docker_gui.sh uses $DIR instead of $HOME
# 5. Dockerfile syntax valid
# 6. Python files don't use hardcoded paths

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

PASS=0
FAIL=0
TOTAL=0

function test_pass() {
    TOTAL=$((TOTAL + 1))
    PASS=$((PASS + 1))
    echo "  [PASS] $1"
}

function test_fail() {
    TOTAL=$((TOTAL + 1))
    FAIL=$((FAIL + 1))
    echo "  [FAIL] $1"
    echo "         Reason: $2"
}

echo "=== Portability Test Suite ==="
echo ""

# Test 1: No hardcoded /home/koko paths in tracked files (excluding test script, README, and build artifacts)
echo "Test 1: Checking for hardcoded paths in tracked files"
RESULT=$(grep -rn '/home/koko' \
    --include='*.py' --include='*.sh' --include='*.launch.py' \
    --include='*.yaml' --include='*.xml' --include='*.md' . \
    2>/dev/null | grep -v 'install/' | grep -v 'build/' | grep -v 'test_portability.sh' | grep -v '.git/' | grep -v 'README.md' | grep -v '## ' || true)
if [ -z "$RESULT" ]; then
    test_pass "No hardcoded /home/koko paths in tracked files"
else
    test_fail "Found hardcoded paths" "$RESULT"
fi
echo ""

# Test 2: env.sh uses dynamic path detection
echo "Test 2: Verifying env.sh uses dynamic path detection"
if [ -f "env.sh" ]; then
    if grep -q 'BASH_SOURCE' env.sh && ! grep -q '/home/koko' env.sh; then
        test_pass "env.sh uses BASH_SOURCE for dynamic path detection"
    else
        test_fail "env.sh does not use dynamic path detection" "No BASH_SOURCE found or hardcoded path present"
    fi
else
    test_fail "env.sh not found" "File env.sh does not exist"
fi
echo ""

# Test 3: run_house_cleaner.sh exists and uses dynamic paths
echo "Test 3: Verifying run_house_cleaner.sh"
if [ -f "run_house_cleaner.sh" ]; then
    if grep -q 'BASH_SOURCE' run_house_cleaner.sh && ! grep -q '/home/koko/house_cleaner_ws' run_house_cleaner.sh; then
        test_pass "run_house_cleaner.sh uses dynamic path detection"
    else
        test_fail "run_house_cleaner.sh has issues" "Not using BASH_SOURCE or has hardcoded paths"
    fi
else
    test_fail "run_house_cleaner.sh not found" "File does not exist"
fi
echo ""

# Test 4: run_docker_gui.sh uses $DIR not $HOME
echo "Test 4: Verifying run_docker_gui.sh volume mount"
if [ -f "run_docker_gui.sh" ]; then
    if grep -q '\$DIR:/workspace' run_docker_gui.sh && ! grep -q '\$HOME/house_cleaner_ws' run_docker_gui.sh; then
        test_pass "run_docker_gui.sh uses \$DIR for volume mount"
    else
        test_fail "run_docker_gui.sh has incorrect volume mount" "Not using \$DIR or still using \$HOME"
    fi
else
    test_fail "run_docker_gui.sh not found" "File does not exist"
fi
echo ""

# Test 5: Dockerfile exists and is valid
echo "Test 5: Verifying Dockerfile"
if [ -f "Dockerfile" ]; then
    if grep -q 'FROM ros:jazzy' Dockerfile; then
        test_pass "Dockerfile uses ROS2 Jazzy base"
    else
        test_fail "Dockerfile base image issue" "Base image not ROS2 Jazzy"
    fi
else
    test_fail "Dockerfile not found" "File does not exist"
fi
echo ""

# Test 6: fake_sim_lyrical_standalone.py uses dynamic paths
echo "Test 6: Verifying fake_sim_lyrical_standalone.py"
PY_FILE="src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py"
if [ -f "$PY_FILE" ]; then
    if grep -q '__file__' "$PY_FILE" && ! grep -q '/home/koko' "$PY_FILE"; then
        test_pass "fake_sim_lyrical_standalone.py uses dynamic path detection"
    else
        test_fail "fake_sim_lyrical_standalone.py path issue" "Not using __file__ or has hardcoded paths"
    fi
else
    test_fail "fake_sim_lyrical_standalone.py not found" "File does not exist at $PY_FILE"
fi
echo ""

# Test 7: Scripts are executable
echo "Test 7: Checking script permissions"
for script in run_house_cleaner.sh run_docker.sh run_docker_gui.sh; do
    if [ -f "$script" ]; then
        if [ -x "$script" ]; then
            test_pass "$script is executable"
        else
            test_fail "$script not executable" "File exists but not marked as executable"
        fi
    fi
done
echo ""

# Test 8: entrypoint.sh exists and is valid
echo "Test 8: Verifying entrypoint.sh"
if [ -f "entrypoint.sh" ]; then
    if grep -q 'headless' entrypoint.sh; then
        test_pass "entrypoint.sh handles headless parameter"
    else
        test_fail "entrypoint.sh missing headless support" "No headless parameter found"
    fi
else
    test_fail "entrypoint.sh not found" "File does not exist"
fi
echo ""

# Test 9: docker-compose.yml exists
echo "Test 9: Verifying docker-compose.yml"
if [ -f "docker-compose.yml" ]; then
    if grep -q 'house_cleaner:jazzy' docker-compose.yml; then
        test_pass "docker-compose.yml configured with correct image"
    else
        test_fail "docker-compose.yml image issue" "Image not set to house_cleaner:jazzy"
    fi
else
    test_fail "docker-compose.yml not found" "File does not exist"
fi
echo ""

# Test 10: README.md exists and contains key sections
echo "Test 10: Verifying README.md"
if [ -f "README.md" ]; then
    if grep -q 'System Requirements' README.md && \
       grep -q 'Docker Setup' README.md && \
       grep -q 'Native Install' README.md && \
       grep -q 'Troubleshooting' README.md; then
        test_pass "README.md has all required sections"
    else
        test_fail "README.md missing sections" "Not all required sections present"
    fi
else
    test_fail "README.md not found" "File does not exist"
fi
echo ""

# Summary
echo "=== Test Summary ==="
echo "Total: $TOTAL"
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ "$FAIL" -eq 0 ]; then
    echo ""
    echo "=== ALL TESTS PASSED ==="
    exit 0
else
    echo ""
    echo "=== SOME TESTS FAILED ==="
    exit 1
fi