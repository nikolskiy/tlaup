package plain;

/** A plain class for the fake javac to hand back; it depends on nothing. */
public final class Plain {
    private Plain() {}

    public static int answer() {
        return 42;
    }
}
