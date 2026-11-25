package tlc2.overrides;

/** Implements the interface directly. */
public class DirectOverrides implements ITLCOverrides {
    @SuppressWarnings("rawtypes")
    @Override
    public Class[] get() {
        return new Class[0];
    }
}
