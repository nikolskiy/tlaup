// For test_signals.py's two-SIGINT scenario: a Java agent whose shutdown hook makes a marker file and then holds
// the JVM's exit. The first SIGINT, forwarded by tlaup as SIGTERM, starts the JVM's shutdown, which the test sees by
// the marker while tlaup and the JVM are both alive; the second SIGINT must then kill the JVM at once (11 R2), long
// before the launcher's grace period would. The test compiles it and packs it as an agent jar itself.
import java.nio.file.Files;
import java.nio.file.Paths;

public final class SlowExit {
    private SlowExit() {}

    public static void premain(String marker) {
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            try {
                Files.createFile(Paths.get(marker));
                Thread.sleep(120_000L);
            } catch (Exception e) {
                // nothing to do: the hook only holds the exit
            }
        }));
    }
}
