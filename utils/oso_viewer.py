from rdflib import Graph, URIRef, RDF
import rich
from rich.console import Console
from rich.table import Table
from argparse import ArgumentParser


if __name__ == "__main__":

    argparser = ArgumentParser(description="Lists class instances in OSO ontology")
    argparser.add_argument("cls", type=str, help="Oso class to show (RFs, sites, platforms, etc.)")
    argparser.add_argument("-f", "--file", type=str, help="Path to the OSO ttl file (by default .emso/oso.ttl", default=".emso/oso.ttl")
    args = argparser.parse_args()

    valid_classes = ["RFs", "sites", "platforms"]

    if args.cls not in valid_classes:
        rich.print(f"[red]Class '{args.cls}' is not valid")
        rich.print(f"Valid classes are: {valid_classes}")
        exit()


    if args.cls.lower() == "platforms":
        class_uri = "https://w3id.org/earthsemantics/OSO#Platform"
    elif args.cls.lower() == "sites":
        class_uri = "https://w3id.org/earthsemantics/OSO#Site"
    elif args.cls.lower() == "rfs":
        class_uri = "https://w3id.org/earthsemantics/OSO#RegionalFacility"
    else:
        raise ValueError("This should not happen")

    # Load your RDF data
    g = Graph()
    g.parse(".emso/oso.ttl", format="turtle")  # or other formats: xml, n3, nt, json-ld

#           #---- BBOX RFs ----#
    #           ?regionalFacility :hasBoundingBox ?bbox .
    #           ?bbox :hasEastLongitude ?east .
    #           ?bbox :hasWestLongitude ?west .
    #           ?bbox :hasNorthLatitude ?north .
    #           ?bbox :hasSouthLatitude ?south .

    # Query for instances

    if args.cls == "RFs":

        query = f"""
      SELECT ?regionalFacility ?label ?east ?west ?north ?south ?depth
        WHERE {{
          ?regionalFacility rdf:type :RegionalFacility .
          ?regionalFacility rdfs:label ?label .
          ?regionalFacility :Regional_Facility_is_part_of_EMSO_ERIC :EMSO .      
          # FILTER(LANG(?label) = "en"  || LANG(?label) = "")
            
          OPTIONAL {{
              ?regionalFacility :maxWaterDepth ?depth .
          }}
          OPTIONAL {{
              #-- Point RFs --#
              ?regionalFacility :hasEastLongitude ?east .
              ?regionalFacility :hasEastLongitude ?west .
              ?regionalFacility :hasNorthLatitude ?north .
              ?regionalFacility :hasNorthLatitude ?south .           
            }}
        
          OPTIONAL {{
              ?regionalFacility :hasBoundingBox ?bbox .
              ?bbox :hasEastLongitude ?east .
              ?bbox :hasWestLongitude ?west .
              ?bbox :hasNorthLatitude ?north .
              ?bbox :hasSouthLatitude ?south .     
            }}
        
          # Get the actual depth
          OPTIONAL {{ }}
          OPTIONAL {{ ?regionalFacility :hasBoundingBox ?bbox }}
        
        }}
        GROUP BY ?regionalFacility
    """

    results = g.query(query)
    table = Table(title="Regional Facilities")

    cols = ["label", "east", "west", "north", "south", "depth"]
    for col in cols:
        table.add_column(col, justify="right", style="cyan", no_wrap=True)

    for i, row in enumerate(results):
        # Use get() method or check for None
        regional_facility = row.regionalFacility
        label = row.label

        east = getattr(row, 'east', None)
        west = getattr(row, 'west', None)
        north = getattr(row, 'north', None)
        south = getattr(row, 'south', None)
        depth = getattr(row, 'depth', None)
        table.add_row(label, east, west, north, south, depth)

    console = Console()
    console.print(table)


    input()
elif args.cls == "platforms":



else:
    pass
    # table = Table(title="Dataset Test Report")
    # table.add_column("Label", justify="left", no_wrap=True, style="cyan")
    # table.add_column("URI", justify="left")
    # instances = []
    # for row in results:
    #     label = str(row.label)
    #     instance = str(row.instance)
    #     if instance in instances:
    #         continue
    #     instances.append(instance)
    #     table.add_row(f"'{row.label}'", row.instance)
    # console = Console()
    # console.print(table)
