#!/usr/bin/env bash
# Automated test script to validate portability fixes
# Run from workspace root: ./test_portability.sh
#
# Tests:
# 1. No hardcoded absolute paths in tracked files
# 2. env.sh works dynamically
# 3. run_house_cleaner.sh is executable and in repo
# 4. run_docker.sh uses $DIR for volume mount and GUI setup
# 5. Dockerfile has Mesa/GL libraries
# 6. All launch files are valid Python syntax
# 7. No external file dependencies
# 8. README references are correct
# 9. Config files are valid YAML
# 10. Collision monitor params present and correct type
# 11. MPPI params under FollowPath (not controller_server level)
# 12. Lifecycle manager includes collision_monitor in node_names

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

# Test 1: No hardcoded /home/koko paths in tracked files
echo "Test 1: Checking for hardcoded paths in tracked files"
RESULT=$(grep -rn '/home/koko' \
    --include='*.py' --include='*.sh' --include='*.yaml' --include='*.yml' \
    --include='*.bash' src/ run_docker.sh run_house_cleaner.sh env.sh entrypoint.sh 2>/dev/null || true)
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
grep -q 'SCRIPT_DIR\|BASH_SOURCE\|dirname' run_house_cleaner.sh
check "run_house_cleaner.sh uses dynamic path detection"

# Test 4: run_docker.sh uses $DIR for volume mount and GUI setup
echo ""
echo "Test 4: Checking run_docker.sh GUI configuration"
grep -q 'SCRIPT_DIR\|BASH_SOURCE\|dirname' run_docker.sh
check "run_docker.sh uses dynamic path detection"
grep -q '\$DIR' run_docker.sh
check "run_docker.sh uses \$DIR for workspace mount"
grep -q 'DISPLAY' run_docker.sh
check "run_docker.sh passes DISPLAY for GUI mode"
grep -q '/tmp/.X11-unix' run_docker.sh
check "run_docker.sh mounts X11 socket"
grep -q '/dev/dri' run_docker.sh
check "run_docker.sh maps GPU device"

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

# Test 7: No external file dependencies
echo ""
echo "Test 7: Checking for external symlinks"
RESULT=$(find . -maxdepth 1 -type l -ls 2>/dev/null || true)
[ -z "$RESULT" ]
check "No external symlinks in workspace root"

# Test 8: README references are correct
echo ""
echo "Test 8: Checking README references"
grep -q 'env\.sh' README.md
check "README references env.sh"
grep -q 'run_docker\.sh' README.md
check "README references run_docker.sh"
grep -q 'xhost' README.md
check "README documents X11 setup requirement"

# Test 9: Config files are valid YAML
echo ""
echo "Test 9: Checking YAML config validity"
python3 -c "import yaml; yaml.safe_load(open('src/house_cleaner_bringup/config/nav2_params.yaml'))"
check "nav2_params.yaml is valid YAML"
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"
check "docker-compose.yml is valid YAML"

# Test 10: Collision monitor params present and correct type
echo ""
echo "Test 10: Checking collision_monitor params"
grep -q 'collision_monitor:' src/house_cleaner_bringup/config/nav2_params.yaml
check "collision_monitor params present"
grep -q 'observation_sources' src/house_cleaner_bringup/config/nav2_params.yaml
check "observation_sources defined for collision_monitor"
python3 -c "
import yaml
with open('src/house_cleaner_bringup/config/nav2_params.yaml') as f:
    cfg = yaml.safe_load(f)
sources = cfg['collision_monitor']['ros__parameters']['observation_sources']
assert isinstance(sources, list), f'observation_sources is {type(sources)}, expected list'
print('observation_sources is string_array')
"
check "observation_sources is string_array (not string)"

# Test 11: MPPI params under FollowPath
echo ""
echo "Test 11: Checking MPPI parameter placement"
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

# Test 12: Lifecycle manager includes collision_monitor
echo ""
echo "Test 12: Checking lifecycle manager config"
python3 -c "
import yaml
with open('src/house_cleaner_bringup/config/nav2_params.yaml') as f:
    cfg = yaml.safe_load(f)
nodes = cfg['lifecycle_manager_navigation']['ros__parameters']['node_names']
assert 'collision_monitor' in nodes, 'collision_monitor missing from lifecycle node_names'
print('collision_monitor in lifecycle manager')
"
# Test 13: setup.py entry points reference existing modules
echo ""
echo "Test 13: Checking setup.py entry points"
python3 -c "
import os
# fake_sim_lyrical entry point should reference the existing module
assert os.path.exists('src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical.py'), \
    'fake_sim_lyrical.py must exist'
with open('src/house_cleaner_bringup/setup.py') as f:
    content = f.read()
assert 'fake_sim_lyrical = house_cleaner_bringup.fake_sim_lyrical:main' in content, \
    'entry point does not match module name'
print('entry points reference correct modules')
"
check "setup.py entry points reference existing modules"

# Test 14: All launch files registered in setup.py data_files
echo ""
echo "Test 14: Checking setup.py launch file registration"
python3 -c "
import os
launch_dir = 'src/house_cleaner_bringup/launch'
for f in os.listdir(launch_dir):
    if os.path.isdir(os.path.join(launch_dir, f)):
        continue
    assert f.endswith('.launch.py'), f
    # Read setup.py and check the file is registered
    with open('src/house_cleaner_bringup/setup.py') as sf:
        content = sf.read()
    assert f in content, f'{f} not registered in setup.py data_files'
print('all launch files registered in setup.py')
"
check "All launch files registered in setup.py data_files"

# Test 15: fake_sim_lyrical_standalone.py raycasts with yaw offset
echo ""
echo "Test 15: Checking fake_sim raycast consistency"
grep -q 'self\.yaw +' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim.py
check "fake_sim.py raycasts with yaw offset"
grep -q 'self\.yaw +' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical.py
check "fake_sim_lyrical.py raycasts with yaw offset"
grep -q 'self\.yaw +' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py
check "fake_sim_lyrical_standalone.py raycasts with yaw offset"

# Test 16: fake_sim_lyrical_standalone.py has complete rotation quaternion
echo ""
echo "Test 16: Checking fake_sim_lyrical_standalone.py rotation quaternion"
grep -q 'rotation\.x = 0' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py
check "fake_sim_lyrical_standalone.py sets rotation.x = 0"
grep -q 'rotation\.y = 0' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py
check "fake_sim_lyrical_standalone.py sets rotation.y = 0"
grep -q 'rotation\.z = math.sin' src/house_cleaner_bringup/house_cleaner_bringup/fake_sim_lyrical_standalone.py
check "fake_sim_lyrical_standalone.py sets rotation.z"

# Test 17: docker-compose.yml has GUI configuration
echo ""
echo "Test 17: Checking docker-compose.yml GUI config"
grep -q 'DISPLAY' docker-compose.yml
check "docker-compose.yml passes DISPLAY for GUI"
grep -q 'LIBGL_ALWAYS_SOFTWARE' docker-compose.yml
check "docker-compose.yml includes software rendering fallback"
grep -q '/tmp/.X11-unix' docker-compose.yml
check "docker-compose.yml mounts X11 socket"
grep -q '/dev/dri' docker-compose.yml
check "docker-compose.yml maps GPU device"

# Test 18: house_cleaner_assistant_lyrical.py low battery return-to-dock
echo ""
echo "Test 18: Checking lyrical assistant low battery behavior"
grep -q 'RETURNING' src/house_cleaner_bringup/house_cleaner_bringup/house_cleaner_assistant_lyrical.py
check "lyrical assistant has RETURNING state for low battery"

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
