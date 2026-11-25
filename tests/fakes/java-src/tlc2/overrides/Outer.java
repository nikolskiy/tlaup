package tlc2.overrides;

/** A nested class that implements the interface: its binary name keeps the $. */
public class Outer {
    public static class Inner implements ITLCOverrides {
        @SuppressWarnings("rawtypes")
        @Override
        public Class[] get() {
            return new Class[0];
        }
    }
}
