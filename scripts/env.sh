# source scripts/env.sh — the laptop runtime: Java 17 (Spark 4.1 dies on Java 23+), loopback only, the repo venv.
_lm_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
if [ -z "${JAVA_HOME:-}" ] || ! "$JAVA_HOME/bin/java" -version 2>&1 | grep -qE 'version "(17|21)\.'; then
  for _j in /opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
            /usr/lib/jvm/java-17-openjdk-amd64 /usr/lib/jvm/java-17-openjdk; do
    [ -x "$_j/bin/java" ] && { export JAVA_HOME="$_j"; break; }
  done
fi
export SPARK_LOCAL_IP=127.0.0.1
export PYSPARK_PYTHON="$_lm_root/.venv/bin/python"
export PYSPARK_DRIVER_PYTHON="$_lm_root/.venv/bin/python"
export PATH="$JAVA_HOME/bin:$_lm_root/.venv/bin:$PATH"
unset _j _lm_root
