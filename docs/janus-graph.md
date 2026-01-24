# Run console

`./console.sh`

# Connect

```
:remote connect tinkerpop.server conf/remote.yaml session
:remote console
```

# Close transactions
graph.getOpenTransactions()
graph.getOpenTransactions().getAt(0).rollback()

# Close ghost instances
m = graph.openManagement();
ids = m.getOpenInstances();
for(String id : ids){if(!id.contains("("){m.forceCloseInstance(id)}};
m.commit();

# Create index
pk = m.makePropertyKey('type').dataType(String.class).make()
// pk = m.getPropertyKey('caption') - for existing properties
m.buildIndex('byCaption', Vertex.class).addKey(pk).buildCompositeIndex()
m.commit()
ManagementSystem.awaitGraphIndexStatus(graph, 'byCaption').call() 

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