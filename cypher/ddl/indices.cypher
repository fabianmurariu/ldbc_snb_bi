// uniqueness constrains (implying an index)
CREATE CONSTRAINT ON (n:City)         ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Comment)      ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Country)      ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Forum)        ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Message)      ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Organisation) ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Person)       ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Post)         ASSERT n.id IS UNIQUE;
CREATE CONSTRAINT ON (n:Tag)          ASSERT n.id IS UNIQUE;

// name/firstName
CREATE INDEX ON :Country(name);
CREATE INDEX ON :Person(firstName);
CREATE INDEX ON :Tag(name);
CREATE INDEX ON :TagClass(name);

// creationDate
CREATE INDEX ON :Message(creationDate);
CREATE INDEX ON :Post(creationDate);
