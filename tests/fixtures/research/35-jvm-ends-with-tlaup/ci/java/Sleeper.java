package q35;

import java.io.FileWriter;

/** Sleeps for args[1] seconds; a shutdown hook appends "hook" to the file args[0], so a log without it means a hard kill. */
public final class Sleeper {
    public static void main(String[] args) throws Exception {
        final String log = args[0];
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try (FileWriter w = new FileWriter(log, true)) {
                w.write("hook t=" + System.currentTimeMillis() + "\n");
            } catch (Exception e) { /* nothing */ }
        }));
        try (FileWriter w = new FileWriter(log, true)) { w.write("main pid=" + ProcessHandle.current().pid() + "\n"); }
        Thread.sleep(Long.parseLong(args.length > 1 ? args[1] : "120") * 1000L);
        try (FileWriter w = new FileWriter(log, true)) { w.write("slept-out\n"); }
    }
}
