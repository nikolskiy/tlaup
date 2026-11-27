package tlaup.lifeline;

import java.util.Optional;

/**
 * Ends this JVM when a given process is gone (tlaup's lifeline, design 20 G3).
 *
 * <p>Started as {@code -javaagent:lifeline.jar=pid=<digits>}. It looks the process up once and keeps the handle,
 * because {@link ProcessHandle#isAlive()} compares the start time as well as the id, so a reused id is not taken
 * for the original process. If the process is already gone, the JVM exits at once; otherwise a daemon thread
 * polls every 500 milliseconds. The agent prints nothing, opens no file and sets no signal handler. An argument
 * that is not {@code pid=<digits>} makes the agent do nothing at all: it never stops a tool by mistake.
 */
public final class Lifeline {
    private static final int EXIT_CODE = 143;
    private static final long POLL_MILLIS = 500;
    private static final String PREFIX = "pid=";

    private Lifeline() {
    }

    /** The agent entry point. No exception leaves it: one would stop the JVM before the tool starts. */
    public static void premain(String args) {
        try {
            Long pid = parse(args);
            if (pid == null) {
                return;
            }
            Optional<ProcessHandle> found = ProcessHandle.of(pid);
            if (!found.isPresent()) {
                System.exit(EXIT_CODE);
                return;
            }
            ProcessHandle handle = found.get();
            Thread watcher = new Thread(() -> watch(handle), "tlaup-lifeline");
            watcher.setDaemon(true);
            watcher.start();
        } catch (Throwable ignored) {
            // Silence is the rule: no stream is touched, and the tool starts as if there were no agent.
        }
    }

    private static Long parse(String args) {
        if (args == null || !args.startsWith(PREFIX)) {
            return null;
        }
        String digits = args.substring(PREFIX.length());
        if (digits.isEmpty() || digits.length() > 18) {
            return null;
        }
        for (int i = 0; i < digits.length(); i++) {
            char c = digits.charAt(i);
            if (c < '0' || c > '9') {
                return null;
            }
        }
        return Long.valueOf(digits);
    }

    private static void watch(ProcessHandle handle) {
        try {
            while (handle.isAlive()) {
                Thread.sleep(POLL_MILLIS);
            }
            System.exit(EXIT_CODE);
        } catch (Throwable ignored) {
            // An interrupted or failed watcher ends quietly; the JVM is left as it was.
        }
    }
}
