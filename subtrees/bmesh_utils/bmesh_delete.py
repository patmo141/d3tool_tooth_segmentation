from bmesh.types import BMesh, BMFace, BMVert, BMEdge

def bmesh_delete(bme:BMesh, geom:list, context:str="VERTS"):
    """

    Parameters:
        bme (BMesh): BMesh object
        geom (list of (BMVert, BMEdge, BMFace)): geometry to remove
        context (enum in ['VERTS', 'EDGES', 'FACES_ONLY', 'EDGES_FACES', 'FACES', 'FACES_KEEP_BOUNDARY', 'TAGGED_ONLY']): geometry types to delete

    Returns:
        None
    """

    verts = set()
    edges = set()
    faces = set()

    for item in geom:
        if isinstance(item, BMVert):
            verts.add(item)
        elif isinstance(item, BMEdge):
            edges.add(item)
        elif isinstance(item, BMFace):
            faces.add(item)

    # Remove geometry
    if context == "VERTS":
        for v in verts:
            bme.verts.remove(v)

    elif context == "EDGES":
        all_verts = set()
        for e in edges:
            all_verts |= set(e.verts)
            bme.edges.remove(e)
        for v in all_verts:
            if len(v.link_edges) == 0:
                bme.verts.remove(v)

    elif context == "FACES_ONLY":
        for f in faces:
            bme.faces.remove(f)

    elif context == "EDGES_FACES":
        remove_faces = set()
        for e in edges:
            remove_faces |= set(e.link_faces)
            bme.edges.remove(e)
        for f in remove_faces:
            if f.is_valid: bme.faces.remove(f)

    elif context.startswith("FACES"):
        all_edges = set()
        remove_edges = set()
        all_verts = set()
        for f in faces:
            remove_edges |= all_edges.intersection(set(f.edges))
            all_edges |= set(f.edges)
            all_verts |= set(f.verts)
            bme.faces.remove(f)
        if context == "FACES":
            all_edges = all_edges - remove_edges
            for e in all_edges:
                if len(e.link_faces) == 0:
                    bme.edges.remove(e)
        for e in remove_edges:
            if e.is_valid: bme.edges.remove(e)
        for v in all_verts:
            if len(v.link_edges) == 0:
                bme.verts.remove(v)

    elif context == "TAGGED_ONLY":
        for v in verts:
            bme.verts.remove(v)
        for e in edges:
            bme.edges.remove(e)
        for f in faces:
            bme.faces.remove(f)


def bmesh_fast_delete(bme:BMesh, verts:list=None, edges:list=None, faces:list=None):
    """

    Parameters:
        bme (BMesh): BMesh object
        geom (list of (BMVert, BMEdge, BMFace)): geometry to remove

    Returns:
        None
    """

    if verts is not None:
        for v in verts:
            if v.is_valid: bme.verts.remove(v)
    if edges is not None:
        for e in edges:
            if e.is_valid: bme.edges.remove(e)
    if faces is not None:
        for f in faces:
            if f.is_valid: bme.faces.remove(f)
