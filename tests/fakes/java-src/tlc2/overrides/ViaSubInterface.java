package tlc2.overrides;

/** Implements ITLCOverrides only through SubInterface. */
public class ViaSubInterface implements SubInterface {
    @SuppressWarnings("rawtypes")
    @Override
    public Class[] get() {
        return new Class[0];
    }
}
