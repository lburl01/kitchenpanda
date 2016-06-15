from flask import Flask, render_template, Response, request
from flask.json import jsonify, dumps
from py2neo import Graph, Node, Relationship
import re
import arrow

app = Flask(__name__)

graph = Graph('http://neo4j:local@localhost:7474/db/data/')

#############
# FUNCTIONS #
#############

def results_dictionizer(results):
    result_query = []
    for row in results:
        result_dict = {}
        for column in results.keys():
            result_dict[column] = row[column]
        result_query.append(result_dict)
    return result_query

def goods_entry_form_parse(form_items):
    fields = ['quantity', 'unit', 'name', 'edate', 'location']
    form_items = dict(form_items)
    data_list = []
    for i in range(1, 6):
        i_str = str(i).zfill(2)
        if form_items['name_' + i_str]:
            row_dict = {}
            for field in fields:
                row_dict[field] = form_items[field + "_" + i_str]
            data_list.append(row_dict)
    return data_list



def goods_entry_form_database(data_list):
    relationship_list = []
    for ing_data in data_list:
        ingredient_node = graph.find_one("Ingredient", property_key="name", property_value = ing_data['name'])
        location_node = graph.find_one("Location", property_key="name", property_value = ing_data['location'])
        import_time = arrow.now().isoformat()
        for i in range(0, int(ing_data['quantity'])):
            inventory_relationship = Relationship(ingredient_node, "LOCATED_IN",
                                                  location_node, unit=ing_data['unit'], added=import_time)
            relationship_list.append(inventory_relationship)

    return graph.create(*relationship_list)

def goods_form_string(dict_data):
    return ' '.join([dict_data['quantity'], dict_data['unit'], dict_data['name']]) + " ({})".format(dict_data['location'])

#########
# PAGES #
#########

@app.route('/')
def index():
    goods_query = """MATCH (i:Ingredient)-[r:LOCATED_IN]->(l)
    RETURN i.name as ingredient, count(r) as count, min(r.added) as oldest, l.name as location
    ORDER BY oldest"""

    goods_results = graph.run(goods_query)

    results_list_goods = results_dictionizer(goods_results)

    for result in results_list_goods:
        result['humanized_date'] = arrow.get(result['oldest']).humanize()
        result['date_string'] = arrow.get(result['oldest']).format('YYYY-MM-DD')

    leftovers_query = """MATCH (i:Leftover)-[r:LOCATED_IN]->(l)
    RETURN i.name as leftover, r.added as added, r.exp_date as exp_date, l.name as location
    ORDER BY added"""

    leftovers_results = graph.run(leftovers_query)

    results_list_leftovers = results_dictionizer(leftovers_results)

    for result in results_list_leftovers:
        result['humanized_date'] = arrow.get(result['added']).humanize()
        result['date_string'] = arrow.get(result['added']).format('YYYY-MM-DD')

    return render_template('index.html', results_list_goods=results_list_goods,
    results_list_leftovers=results_list_leftovers)

@app.route('/goods/')
def goods():
    query = """MATCH (i:Ingredient)-[r:LOCATED_IN]->(l)
    RETURN i.name as ingredient, count(r) as count, min(r.added) as oldest, l.name as location
    ORDER BY oldest"""

    goods_results = graph.run(query)

    results_list = results_dictionizer(goods_results)

    for result in results_list:
        result['humanized_date'] = arrow.get(result['oldest']).humanize()
        result['date_string'] = arrow.get(result['oldest']).format('YYYY-MM-DD')

    return render_template('goods.html', goods_results=results_list)

@app.route('/goods/enter/', methods=['GET', 'POST'])
def goods_enter():
    if request.method == "POST":
        form_data = [i for i in request.form.items()]
        data_list = goods_entry_form_parse(form_data)
        goods_entry_form_database(data_list)
        items_added_list = [goods_form_string(item) for item in data_list]
        items_added_string = ', '.join(items_added_list)
        return render_template('goods_enter.html', items_added_string = items_added_string)
    else:
        return render_template('goods_enter.html')

@app.route('/goods/remove/')
def goods_remove():
    return render_template('goods_remove.html')

@app.route('/leftovers/')
def leftovers():
    query = """MATCH (i:Leftover)-[r:LOCATED_IN]->(l)
    RETURN i.name as leftover, r.added as added, r.exp_date as exp_date, l.name as location
    ORDER BY added"""

    goods_results = graph.run(query)

    results_list = results_dictionizer(goods_results)

    for result in results_list:
        result['humanized_date'] = arrow.get(result['added']).humanize()
        result['date_string'] = arrow.get(result['added']).format('YYYY-MM-DD')

    return render_template('leftovers.html', leftovers_results=results_list)

@app.route('/leftovers/enter/', methods=['GET', 'POST'])
def leftovers_enter():
    if request.method == "POST":
        dqr2
        return render_template('leftovers_enter.html', leftovers_added_string = leftovers_added_string)
    else:
        return render_template('leftovers_enter.html')

@app.route('/leftovers/eat/', methods=['GET', 'POST'])
def leftovers_eat():
    if request.method == "POST":
        form_data = [i for i in request.form.items()]
        form_data = dict(form_data)
        name = form_data['leftover_01']
        location = form_data['location_01']
        if location == '':
            location = None
        import_time = arrow.now().isoformat()
        query = """MATCH (l:Leftover {name: {name}})-[r:LOCATED_IN]->(loc:Location), (a:Location {name: 'Archive'})
        OPTIONAL MATCH (l:Leftover)-[r:LOCATED_IN]-(loc:Location {name : {location}})
        DELETE r
        CREATE (l)-[:ARCHIVED {added: {import_time}}]->(a)
        RETURN l.name
        """
        results = graph.run(query, name=name, location=location, import_time=import_time)
        leftover_removed_string = results[0]

        return render_template('leftovers_remove.html', leftover_removed_string=leftover_removed_string)
    else:
        return render_template('leftovers_remove.html')

@app.route('/goods/equivalence/')
def goods_equivalence():
    return render_template('admin_similar.html')

@app.route('/goods/substitution/')
def goods_substitution():
    return render_template('admin_similar.html')

#################
# API ENDPOINTS #
#################

@app.route('/ingredients_search/<ingredient>/')
def ingredients(ingredient):
    ingredient_re = r".*" + ingredient + r".*"

    query = """MATCH (n:Ingredient)
    WHERE n.name =~ {ingredient_re}
    RETURN n.name as ingredient"""

    results = graph.run(query, ingredient_re=ingredient_re)
    results_list = [i['ingredient'] for i in results]
    #json_list = jsonify(results_list)
    return Response(dumps(results_list),  mimetype='application/json')


@app.route('/ingredients/all/')
def all_ingredients():
    query = """MATCH (n:Ingredient)
    RETURN n.name as ingredient
    ORDER BY n.rank"""

    results = graph.run(query)
    results_list = [i['ingredient'] for i in results]

    return Response(dumps(results_list),  mimetype='application/json')

@app.route('/ingredients/in_stock/')
def in_stock_ingredients():
    query = """MATCH (i)-[r:LOCATED_IN]->()
    RETURN i.name as ingredient, sum(r.quantity) as quantity
    ORDER BY quantity DESC"""

    results = graph.run(query)

    results_list = [i['ingredient'] for i in results]

    return Response(dumps(results_list),  mimetype='application/json')

@app.route('/leftovers/in_stock/')
def in_stock_leftovers():
    query = """MATCH (i:Leftover)-[r:LOCATED_IN]->()
    RETURN i.name as leftover"""

    results = graph.run(query)

    results_list = [i['leftover'] for i in results]

    return Response(dumps(results_list),  mimetype='application/json')

if __name__ == '__main__':
	app.run(port=1111, debug=True)
