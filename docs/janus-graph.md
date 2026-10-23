# Index management without the console

`scripts/create_index.py` does the whole dance over the ordinary driver, with the
credentials from `.env`, so it does not depend on the console container at all:

```
python scripts/create_index.py --property sourceKey
python scripts/create_index.py --property sourceKey --close-stale-instances --apply
```

Dry run first: it prints the current indexes, the state of the property key, how
many vertices carry it, and the live and stale instances. Management operations
work through plain script submissions (`graph.openManagement()` server-side), only
with fully qualified class names, since the server's script engine imports less
than the console's `janusgraph.imports` plugin.

# Run console

`./console.sh`

# Connect

```
:remote connect tinkerpop.server conf/remote.yaml session
:remote console
```

The server requires authentication, so `conf/remote.yaml` **must** carry
`username` and `password`. `:remote connect` succeeds either way — SASL only
starts with the first request — so a missing password shows up later as
`Failure to initialize security context` on whatever you type first, management
or not. The file lives inside the console container, so mount it from the host:
on a container rebuild the image's own copy comes back without the credentials.

# Close transactions
graph.getOpenTransactions()
graph.getOpenTransactions().getAt(0).rollback()

# Close ghost instances

Each server run registers an instance and an unclean stop leaves it behind; 28 had
piled up by October 2026. They block `REGISTER_INDEX`, which waits for every open
instance to acknowledge the new index — the wait then never ends. Safe to close
while the backend is single-process (`berkeleyje`): everything except `(current)`
is dead.

```groovy
m = graph.openManagement()
m.getOpenInstances().findAll { !it.contains('(current)') }.each { m.forceCloseInstance(it) }
m.commit()
```

# Create index
pk = m.makePropertyKey('type').dataType(String.class).make()
// pk = m.getPropertyKey('caption') - for existing properties
m.buildIndex('byCaption', Vertex.class).addKey(pk).buildCompositeIndex()
m.commit()
ManagementSystem.awaitGraphIndexStatus(graph, 'byCaption').call()

// An index over a key nothing carries yet needs no reindex scan:
// m.updateIndex(m.getGraphIndex('bySourceKey'), SchemaAction.ENABLE_INDEX)
// A key created in the *same* transaction as the index is ENABLED at once.

# Indexes as of October 2026
// byCaption          caption      ENABLED
// byType             type         ENABLED
// verseByImportIndex importIndex  ENABLED
// bySourceKey        sourceKey    ENABLED

# Reindex new index
m = graph.openManagement()
m.updateIndex(m.getGraphIndex("byCaption"), SchemaAction.REINDEX).get()
m.commit()

i  = m.getGraphIndex('byVerseImportIndex')
pk = m.getPropertyKey('importIndex')
i.getIndexStatus(pk)

m.updateIndex(i, SchemaAction.DISABLE_INDEX)
m.printIndexes()

ManagementSystem.awaitGraphIndexStatus(graph, 'byImportIndexComposite').call()
