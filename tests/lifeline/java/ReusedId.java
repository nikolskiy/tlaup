import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * Runs inside a small process-id namespace. Takes a handle on a process as the agent does, ends that process,
 * starts processes that take the same id, and checks that the old handle is no longer alive.
 */
public class ReusedId {
    private static final int TRIES = 20;

    public static void main(String[] args) throws Exception {
        Process first = new ProcessBuilder("sleep", "600").inheritIO().start();
        long pid = first.pid();
        ProcessHandle handle = ProcessHandle.of(pid).get();
        if (!handle.isAlive()) {
            throw new IllegalStateException("the handle of a running process is not alive");
        }
        first.destroyForcibly();
        first.waitFor();
        for (int i = 0; i < TRIES; i++) {
            // The next process takes the id after this one.
            Files.write(Paths.get("/proc/sys/kernel/ns_last_pid"), Long.toString(pid - 1).getBytes());
            Process again = new ProcessBuilder("sleep", "600").inheritIO().start();
            try {
                if (again.pid() != pid) {
                    continue;
                }
                if (!ProcessHandle.of(pid).get().isAlive()) {
                    throw new IllegalStateException("the process that reuses the id is not alive");
                }
                System.out.println(handle.isAlive() ? "ALIVE" : "GONE");
                return;
            } finally {
                again.destroyForcibly();
                again.waitFor();
            }
        }
        System.out.println("NO-REUSE");
    }
}
