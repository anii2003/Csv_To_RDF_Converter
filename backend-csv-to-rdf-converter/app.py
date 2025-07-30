from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
from rdflib import Graph, URIRef, Literal, Namespace, RDF, XSD
import os, json, re
import unicodedata

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
OUTPUT_FILE = "output.ttl"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/convert', methods=['POST'])
def convertir_csv_a_rdf():
    csv_file = request.files.get('csv')
    json_file = request.files.get('json')

    if not csv_file or not json_file:
        return jsonify({"error": "Archivos CSV y JSON requeridos."}), 400

    csv_path = os.path.join(UPLOAD_FOLDER, "data.csv")
    json_path = os.path.join(UPLOAD_FOLDER, "mapeo.json")
    csv_file.save(csv_path)
    json_file.save(json_path)

    try:
        rdf_output_path = os.path.join(UPLOAD_FOLDER, OUTPUT_FILE)
        convertir(csv_path, json_path, rdf_output_path)
        return send_file(rdf_output_path, as_attachment=True, mimetype="text/turtle")
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def convertir(CSV_PATH, JSON_PATH, OUTPUT_TTL):
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)


    multi_separator = config.get("multi_value_separator", ";")

    def limpiar_uri(valor):
        valor = unicodedata.normalize('NFKD', str(valor).strip()).encode('ascii', 'ignore').decode('ascii')
        valor = re.sub(r"[^\w\-]", "_", valor)
        valor = re.sub(r"_+", "_", valor)
        return valor.strip("_")

    def make_uri(valor, columna, base_uri, reglas_uri):
        valor = str(valor).strip()
        prefijo = reglas_uri.get(columna, "")
        if prefijo:
            return URIRef(prefijo + valor)
        return URIRef(base_uri + limpiar_uri(valor))

    df = pd.read_csv(CSV_PATH)

    if "key_column" not in config or config["key_column"] not in config["properties"]:
        raise Exception("Debe definirse correctamente 'key_column' en el JSON.")
    if "res" not in config["prefixes"]:
        raise Exception("Debe incluirse el prefijo 'res' para URIs base.")

    g = Graph()
    namespaces = {}
    for prefix, uri in config["prefixes"].items():
        ns = Namespace(uri)
        namespaces[prefix] = ns
        g.bind(prefix, ns)

    BASE_URI = config["prefixes"]["res"]
    clave_columna = config["key_column"]
    uri_rules = config.get("uri_rules", {})

    boolean_map_config = config.get("boolean_map", {})
    boolean_columns = set(boolean_map_config.get("columns", []))
    true_vals = set(map(str.lower, boolean_map_config.get("true_values", [])))
    false_vals = set(map(str.lower, boolean_map_config.get("false_values", [])))

    clases_rdf = {}
    for entidad, data in config.get("classes", {}).items():
        if "typeProperty" not in data:
            raise Exception(f"Falta 'typeProperty' para la clase '{entidad}' en el JSON.")
        type_prop = data["typeProperty"]
        pfx, name = type_prop.split(":")
        prop_rdf = namespaces[pfx][name]
        clases_rdf[entidad] = []
        for tipo in data.get("types", []):
            pfx2, clase = tipo.split(":")
            clases_rdf[entidad].append((prop_rdf, namespaces[pfx2][clase]))

    mapeo_columnas = {}
    entidades = {}

    for col, data in config["properties"].items():
        prefix, nombre_prop = data["predicate"].split(":")
        tipo_xsd = data["type"].split(":")[1]
        entidad = data.get("entity")
        lang = data.get("lang")

        predicado = namespaces[prefix][nombre_prop]
        datatype = getattr(XSD, tipo_xsd, XSD.string)

        mapeo_columnas[col] = (predicado, datatype, entidad, lang)
        if entidad:
            entidades.setdefault(entidad, []).append(col)

    entidad_principal = mapeo_columnas[clave_columna][2]

    for _, fila in df.iterrows():
        if pd.isna(fila[clave_columna]):
            continue

        recurso_principal_uri = make_uri(fila[clave_columna], clave_columna, BASE_URI, uri_rules)
        usados = set()

        for prop_rdf, clase in clases_rdf.get(entidad_principal, []):
            g.add((recurso_principal_uri, prop_rdf, clase))

        for entidad, columnas in entidades.items():
            if entidad == entidad_principal:
                continue

            items_por_entidad = {}
            total = 0
            for col in columnas:
                if col in fila and pd.notna(fila[col]):
                    valores = [v.strip() for v in str(fila[col]).split(multi_separator) if v.strip()]
                    items_por_entidad[col] = valores
                    total = max(total, len(valores))

            for i in range(total):
                base = items_por_entidad.get(columnas[0], [f"{entidad}_{i}"])[i] if i < len(items_por_entidad.get(columnas[0], [])) else f"{entidad}_{i}"
                entidad_uri = URIRef(BASE_URI + limpiar_uri(base))

                for prop_rdf, clase in clases_rdf.get(entidad, []):
                    g.add((entidad_uri, prop_rdf, clase))

                relaciones = config.get("relationships", {})
                if entidad in relaciones:
                    prefix, pred_name = relaciones[entidad].split(":")
                    predicado_relacion = namespaces[prefix][pred_name]
                    g.add((recurso_principal_uri, predicado_relacion, entidad_uri))

                for col in columnas:
                    pred, dtype, _, lang = mapeo_columnas[col]
                    if i < len(items_por_entidad.get(col, [])):
                        valor = items_por_entidad[col][i]
                        if dtype == XSD.string and lang:
                            g.add((entidad_uri, pred, Literal(valor, lang=lang)))
                        else:
                            g.add((entidad_uri, pred, Literal(valor, datatype=dtype)))
                        usados.add(col)

        for col, val in fila.items():
            if col not in mapeo_columnas or pd.isna(val) or col in usados or col == clave_columna:
                continue

            pred, dtype, _, lang = mapeo_columnas[col]
            val = str(val).strip()

            if multi_separator in val:
                for v in val.split(multi_separator):
                    v = v.strip()
                    if not v:
                        continue
                    if dtype == XSD.string and lang:
                        g.add((recurso_principal_uri, pred, Literal(v, lang=lang)))
                    elif dtype == XSD.anyURI:
                        g.add((recurso_principal_uri, pred, URIRef(BASE_URI + limpiar_uri(v))))
                    else:
                        g.add((recurso_principal_uri, pred, Literal(v, datatype=dtype)))
            else:
                try:
                    if dtype == XSD.anyURI:
                        obj = URIRef(BASE_URI + limpiar_uri(val))
                    elif dtype == XSD.decimal:
                        obj = Literal(float(val), datatype=dtype)
                    elif dtype == XSD.gYear:
                        obj = Literal(int(float(val)), datatype=dtype)
                    elif dtype == XSD.integer:
                        obj = Literal(int(val), datatype=dtype)
                    elif dtype == XSD.boolean and col in boolean_columns:
                        val_lower = val.lower()
                        obj = Literal(True if val_lower in true_vals else False if val_lower in false_vals else val, datatype=dtype)
                    elif dtype == XSD.string and lang:
                        obj = Literal(val, lang=lang)
                    else:
                        obj = Literal(val, datatype=dtype)
                except:
                    obj = Literal(val, datatype=XSD.string)
                g.add((recurso_principal_uri, pred, obj))

    print(list(g.namespaces()))
    g.serialize(destination=OUTPUT_TTL, format="turtle")
    print(f"RDF exportado correctamente a '{OUTPUT_TTL}'")

if __name__ == "__main__":
    app.run(debug=True)
