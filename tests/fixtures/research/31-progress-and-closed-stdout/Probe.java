import java.io.PrintStream;
/** Runs TLC in-process and, when it returns, reports System.out/System.err checkError() on a side file. */
public class Probe {
    public static void main(String[] args) throws Exception {
        int rc = 0;
        try {
            tlc2.TLC tlc = new tlc2.TLC();
            if (tlc.handleParameters(args)) { rc = tlc.process(); }
        } catch (Throwable t) { System.err.println("probe: exception " + t); }
        try (PrintStream side = new PrintStream("probe-result.txt")) {
            side.println("System.out.checkError() = " + System.out.checkError());
            side.println("System.err.checkError() = " + System.err.checkError());
            side.println("tlc.process returned (before System.exit) = " + rc);
        }
    }
}
