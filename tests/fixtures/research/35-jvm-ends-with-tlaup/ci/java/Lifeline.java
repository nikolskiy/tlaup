package q35;

import java.io.FileInputStream;
import java.io.FileWriter;
import java.io.InputStream;
import java.util.Optional;

/**
 * Experiment agent for research question 35: end this JVM when the process that started it is gone.
 *
 *   -javaagent:lifeline.jar=MODE[,log=FILE][,interval=MS][,code=N]
 *
 * MODE is one of
 *   pipe=PATH   read PATH (an inherited pipe, /dev/fd/N) until end of file
 *   stdin       read System.in until end of file
 *   pid=N       poll ProcessHandle.of(N).isAlive() every interval ms (default 500)
 *   onexit=N    wait on ProcessHandle.of(N).onExit()
 *
 * When the watched thing ends, it writes one line to the log file (if given) and calls System.exit(code),
 * default 143, so shutdown hooks run as they do after SIGTERM.
 */
public final class Lifeline {
    public static void premain(String args) { start(args == null ? "" : args); }
    public static void agentmain(String args) { premain(args); }

    private static String log;
    private static int code = 143;

    private static void note(String what) {
        if (log == null) return;
        try (FileWriter w = new FileWriter(log, true)) {
            w.write("lifeline " + what + " t=" + System.currentTimeMillis() + "\n");
        } catch (Exception e) { /* nothing to do */ }
    }

    private static void start(String args) {
        String mode = null, value = null;
        long interval = 500;
        for (String part : args.split(",")) {
            if (part.isEmpty()) continue;
            int eq = part.indexOf('=');
            String k = eq < 0 ? part : part.substring(0, eq);
            String v = eq < 0 ? "" : part.substring(eq + 1);
            switch (k) {
                case "log": log = v; break;
                case "interval": interval = Long.parseLong(v); break;
                case "code": code = Integer.parseInt(v); break;
                default: mode = k; value = v;
            }
        }
        final String m = mode, val = value;
        final long iv = interval;
        Thread t = new Thread(() -> run(m, val, iv), "lifeline");
        t.setDaemon(true);
        t.start();
        note("started mode=" + m);
    }

    private static void run(String mode, String value, long interval) {
        try {
            if ("pipe".equals(mode) || "stdin".equals(mode)) {
                InputStream in = "stdin".equals(mode) ? System.in : new FileInputStream(value);
                byte[] buf = new byte[256];
                while (in.read(buf) >= 0) { /* data is not expected; keep reading until EOF */ }
                note("eof");
            } else if ("pid".equals(mode)) {
                Optional<ProcessHandle> p = ProcessHandle.of(Long.parseLong(value));
                while (p.isPresent() && p.get().isAlive()) Thread.sleep(interval);
                note(p.isPresent() ? "parent-gone" : "parent-gone-at-start");
            } else if ("onexit".equals(mode)) {
                Optional<ProcessHandle> p = ProcessHandle.of(Long.parseLong(value));
                if (p.isPresent()) p.get().onExit().join();
                note(p.isPresent() ? "parent-gone" : "parent-gone-at-start");
            } else {
                note("unknown-mode " + mode);
                return;
            }
        } catch (Exception e) {
            note("error " + e);
        }
        System.exit(code);
    }
}
