import java.nio.file.Files;
import java.nio.file.Paths;

/** Writes its first argument as a file to say it is up, then sleeps; with a second argument it ends at once. */
public class Sleeper {
    public static void main(String[] args) throws Exception {
        Files.write(Paths.get(args[0]), new byte[] {'u', 'p'});
        if (args.length > 1) {
            return;
        }
        Thread.sleep(600_000);
    }
}
