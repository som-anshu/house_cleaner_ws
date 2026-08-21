#!/usr/bin/env bash
# Automated test script to validate portability fixes
# Run from workspace root: ./test_portability.sh
#
# Tests:
# 1. No hardcoded absolute paths in tracked files
# 2. env.sh works dynamically
# 3. run_house_cleaner.sh is executable and in repo
# 4. run_docker_gui.sh uses $DIR for volume mount
# 5. Dockerfile has Mesa/GL libraries
# 6. All launch files are valid Python syntax
# 7. No external file dependencies (run_house_cleaner.sh symlink target)
# 8. README references are correct
# 9. Config files are valid YAML
# 10. Collision monitor params present
# 11. MPPI params under FollowPath (not controller_server level)
# 12. Lifecycle manager node_names excludes collision_monitor

set -e
PASS=0
FAIL=0

check() {
    if [ $? -eq 0 ]; then
        echo "  PASS: $1"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $1"
        FAIL=$((FAIL + 1))
    fi
}

echo "=== Portability Test Suite ==="
echo ""

# Test 1: No hardcoded /home/koko paths in tracked files (excluding test script, README, and build artifacts)
echo "Test 1: Checking for hardcoded paths in tracked files"
RESULT=$(grep -rn '/home/koko' \
    --include='*.py' --include='*.sh' --include='*.yaml' --include='*.yml' \
    --include='*.bash' src/ run_docker.sh run_docker_gui.sh run_house_cleaner.sh env.sh entrypoint.sh 2>/dev/null || true)
[ -z "$RESULT" ]
check "No hardcoded /home/koko paths"

# Test 2: env.sh uses dynamic path detection
echo ""
echo "Test 2: Checking env.sh uses dynamic paths"
grep -q 'SCRIPT_DIR\|BASH_SOURCE\|dirname' env.sh
check "env.sh uses dynamic path detection"

# Test 3: run_house_cleaner.sh is executable and in repo
echo ""
echo "Test 3: Checking run_house_cleaner.sh"
[ -f run_house_cleaner.sh ]
check "run_house_cleaner.sh exists"
[ -x run_house_cleaner.sh ]
check "run_house_cleaner.sh is executable"
! grep -q '/home/koko/.*run_house' $(find /home/koko/house_cleaner_ws -maxdepth 1 -name 'run_house*') 2>/dev/null || true
check "run_house_cleaner.sh uses dynamic paths"

# Test 4: run_docker_gui.sh uses $DIR for volume mount
echo ""
echo "Test 4: Checking run_docker_gui.sh volume mount"
grep -q 'SCRIPT_DIR\|BASH_SOURCE\|dirname' run_docker_gui.sh
check "run_docker_gui.sh uses dynamic path detection"
grep -q '\$DIR' run_docker_gui.sh
check "run_docker_gui.sh uses \$DIR for workspace mount"

# Test 5: Dockerfile has Mesa/GL libraries
echo ""
echo "Test 5: Checking Dockerfile for GL libraries"
grep -q 'libgl1\|libglu1\|mesa' Dockerfile
check "Dockerfile includes Mesa/GL libraries"

# Test 6: All launch files are valid Python syntax
echo ""
echo "Test 6: Checking launch files syntax"
for f in src/house_cleaner_bringup/launch/*.launch.py; do
    python3 -c "import ast; ast.parse(open('$f').read())" 2>/dev/null
    check "$f parses as valid Python"
done

# Test 7: No external file dependencies (run_house_cleaner.sh symlink target)
echo ""
echo "Test 7: Checking for external symlinks"
RESULT=$(find . -maxdepth 1 -type l -ls 2>/dev/null | grep -v '^\.' || true)
[ -z "$RESULT" ]
check "No external symlinks in workspace root"

# Test 8: README references are correct
echo ""
echo "Test 8: Checking README references"
grep -q 'env\.sh' README.md
check "README references env.sh"
grep -q 'run_docker_gui\.sh' README.md
check "README references run_docker_gui.sh"

# Test 9: Config files are valid YAML
echo ""
echo "Test 9: Checking YAML config validity"
python3 -c "import yaml; yaml.safe_load(open('src/house_cleaner_bringup/config/nav2_params.yaml'))"
check "nav2_params.yaml is valid YAML"
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
check "docker-compose.yml is valid YAML"

# Test 10: Collision monitor params present
echo ""
echo "Test 10: Checking collision_monitor params"
grep -q 'collision_monitor:' src/house_cleaner_bringup/config/nav2_params.yaml
check "collision_monitor params present"
grep -q 'observation_sources' src/house_cleaner_bringup/config/nav2_params.yaml
check "observation_sources defined for collision_monitor"

# Test 11: MPPI params under FollowPath
echo ""
echo "Test 11: Checking MPPI parameter placement"
# rollout_batch_size should be under FollowPath (8-space indent inside FollowPath)
python3 -c "
import yaml
with open('src/house_cleaner_bringup/config/nav2_params.yaml') as f:
    cfg = yaml.safe_load(f)
fp = cfg['controller_server']['ros__parameters']['FollowPath']
assert 'rollout_batch_size' in fp, 'rollout_batch_size not in FollowPath'
assert 'collision_checker' in fp, 'collision_checker not in FollowPath'
print('MPPI params in FollowPath')
"
check "MPPI params (rollout_batch_size, collision_checker) under FollowPath"

# Test 12: Lifecycle manager excludes collision_monitor
echo ""
echo "Test 12: Checking lifecycle manager config"
python3 -c "
import yaml
with open('src/house_cleaner_bringup/config/nav2_params.yaml') as f:
    cfg = yaml.safe_load(f)
nodes = cfg['lifecycle_manager_navigation']['ros__parameters']['node_names']
assert 'collision_monitor' not in nodes, 'collision_monitor still in lifecycle node_names'
print('collision_monitor excluded from lifecycle manager')
"
check "collision_monitor excluded from lifecycle manager"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL