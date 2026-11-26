package tlc2.overrides;

/** Reaches the interface only through its superclass. */
public class InheritedOverrides extends AbstractOverrides {
    @SuppressWarnings("rawtypes")
    @Override
    public Class[] get() {
        return new Class[0];
    }
}
