################################################################################
#
# This program is free software: you can redistribute it and/or modify it under 
# the terms of the GNU General Public License as published by the Free Software 
# Foundation, either version 3 of the License, or (at your option) any later 
# version.
# 
# This program is distributed in the hope that it will be useful, but WITHOUT 
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS 
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along with 
# this program. If not, see <https://www.gnu.org/licenses/>. 
#
# Copyright 2025 Nelson R. Salinas
#
################################################################################

#TODO###########################################################################
#TODO Routine to select latest geocoding per occurrence
#TODO Include date and time to file name that is downloaded in a search query
#TODO 
#TODO###########################################################################

import re
from functools import reduce
import datetime
import pytz
from unidecode import unidecode
from io import StringIO

from rapidfuzz import fuzz,process,distance
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text # type: ignore

today = datetime.datetime.now()
yesterday = today - datetime.timedelta(1)
today_date = datetime.date(today.year, today.month, today.day)
yesterday_date = datetime.date(yesterday.year, yesterday.month, yesterday.day)
tz = pytz.timezone('America/Bogota')

locs = [
	"Usaquén",
	"Chapinero"
	"Santa Fe",
	"San Cristóbal",
	"Usme",
	"Tunjuelito",
	"Bosa",
	"Kennedy",
	"Fontibón",
	"Engativá",
	"Suba",
	"Barrios Unidos",
	"Teusaquillo",
	"Los Mártires",
	"Antonio Nariño",
	"Puente Aranda",
	"La Candelaria",
	"Rafael Uribe Uribe",
	"Ciudad Bolívar",
	"Sumapaz"
]

if not "username" in st.session_state: st.session_state.username = ""
if not "password" in st.session_state: st.session_state.password = ""
if not "connection" in st.session_state: st.session_state.connection = None
if not "consulta" in st.session_state: st.session_state.consulta = None
if not "query" in st.session_state: st.session_state.query = None
if not "colector_posible" in st.session_state: st.session_state.colector_posible = []
if not "colector_pre" in st.session_state: st.session_state.colector_pre = None
if not "colectores" in st.session_state: st.session_state.colectores = []
if not "taxon_pre" in st.session_state: st.session_state.taxon_pre = None
if not "taxon_posible" in st.session_state: st.session_state.taxon_posible = []
if not "taxon" in st.session_state: st.session_state.taxa = []
if not "download" in st.session_state: st.session_state.download = False
if not "dwc" in st.session_state: st.session_state.dwc = None
if not "indata" in st.session_state: st.session_state.indata = None
if not "upcsv" in st.session_state: st.session_state.upcsv = None
if not "coll_map" in st.session_state: st.session_state.coll_map = None

@st.dialog("Error")
def error_window(message):
	st.write(message)


#def validate_user_debug():
#	st.session_state.connection = True


def validate_user():

	conn_str = "mysql+mysqlconnector://" + \
	f"{st.session_state.username}:" + \
	f"{st.session_state.password}" + \
	"@localhost:3306/Mutis"

	try:
		engine = create_engine(conn_str)
		st.session_state.connection = engine.connect()

	except:
		error_window("No se pudo establecer conexión a la base de datos `Mutis`. Verifique sus credenciales.")
		st.session_state.connection = None

def validate_consulta():
	pass

def close_db():
	if st.session_state.connection:
		st.session_state.connection.close()
		st.session_state.connection = None


def occurrence_pool(identification_ids):
	ids_str = ", ".join([str(i) for i in identification_ids])
	query = f"SELECT OccurrenceID FROM Occurrrences LEFT JOIN Identifications ON Identifications.Occurrence = Occurrences.OccurrenceID WHERE IdentificationID IN ({ids_str})"
	occ_ids = pd.read_sql_query(query, st.session_state.connection).OccurrenceID.tolist()
	return occ_ids


def get_family(row, tax):
	#tax = pd.read_sql_table("Taxa", st.session_state.connection)
	if row.taxonRank == 'family':
		return row.scientificName
	elif row.genus:
		thpapa = tax.loc[tax.Name == row.genus, 'Parent'].item()
		return tax.loc[tax.TaxonID == thpapa, 'Name'].item()
	else:
		return None
		

def set_taxonomic_fields(rec_table : pd.DataFrame):
	rec_table["taxonRank"] = None
	rec_table['genus'] = None
	rec_table['specificEpithet'] = None
	rec_table['infraspecificEpithet'] = None
	rec_table.loc[rec_table.scientificName.str.contains(' var. ', regex=False), 'taxonRank'] = 'variety'
	rec_table.loc[rec_table.scientificName.str.contains(' subsp. ', regex=False), 'taxonRank'] = 'subspecies'
	rec_table.loc[rec_table.scientificName.str.contains(' fo?\\. ', regex=True), 'taxonRank'] = 'forma'

	if rec_table.loc[rec_table.scientificName.str.contains('ales$', na=False)
		].shape[0] > 0:

		rec_table.loc[
			rec_table.scientificName.str.contains('ales$', na=False),
			'taxonRank'] = 'order'
		
	if rec_table.loc[rec_table.scientificName.str.contains('aceae$', na=False)
		].shape[0] > 0:

		rec_table.loc[
			rec_table.scientificName.str.contains('aceae$', na=False),
			'taxonRank'] = 'family'
		
	if rec_table.loc[rec_table.scientificName.str.contains('×', na=False)
		].shape[0] > 0:

		rec_table.loc[
			rec_table.scientificName.str.contains('×', na=False),
			'taxonRank'] = 'hybrid'
		
	rec_table.loc[
		rec_table.taxonRank.isnull() &
		rec_table.scientificName.str.contains('[\\w\\-]\\s+[\\w\\-]', regex=True),
		'taxonRank'] = 'species'

	# everything else is ided to genus level
	if rec_table.loc[rec_table.taxonRank.isnull()].shape[0] > 0:
		rec_table.loc[rec_table.taxonRank.isnull(), 'taxonRank'] = 'genus'

	rec_table.loc[rec_table.taxonRank == 'species', 'specificEpithet'
		] = rec_table.loc[rec_table.taxonRank == 'species', 'scientificName'
		].str.extract('\\s+([\\w\\-]+)$')[0]

	rec_table.loc[rec_table.taxonRank.isin(['variety', 'forma', 'subspecies']), 'specificEpithet'
		] = rec_table.loc[rec_table.taxonRank.isin(['variety', 'forma', 'subspecies']), 'scientificName'
		].str.extract('\\s+([\\w\\-]+)\\s+[\\w\\-]+$')

	rec_table.loc[rec_table.taxonRank.isin(['variety', 'forma', 'subspecies']), 'infraspecificEpithet'
		] = rec_table.loc[rec_table.taxonRank.isin(['variety', 'forma', 'subspecies']), 'scientificName'
		].str.extract('\\s+[\\w\\-]+\\s+([\\w\\-]+)$')

	rec_table.loc[rec_table.taxonRank == 'genus', 'genus'
		] = rec_table.loc[rec_table.taxonRank == 'genus', 'scientificName']

	rec_table.loc[
		rec_table.taxonRank.isin(['species', 'hybrid', 'variety', 'forma', 'subspecies']),
		'genus'
		] = rec_table.loc[
		rec_table.taxonRank.isin(['species', 'hybrid', 'variety', 'forma', 'subspecies'])
		].scientificName.str.replace('×', ' '
		).str.replace('^\\s+|\\s+$', '', regex=True
		).str.replace('\\s+', ' ', regex=True
		).str.split('\\s+', expand=True
		)[0]

	tax = pd.read_sql_table("Taxa", st.session_state.connection)
	rec_table['family'] = rec_table.apply(lambda x: get_family(x, tax), axis=1)

	return rec_table


def literature_fields(rec_table : pd.DataFrame):

	authlist = ', '.join([
		str(x) for x in rec_table.groupby('refAuthor'
			).size(
			).reset_index(
			).refAuthor.tolist()
	])

	authors = pd.read_sql(
		"SELECT People, LastName, `Order` FROM PeoplePersons " \
		+ "LEFT JOIN Persons ON PeoplePersons.Person=Persons.PersonID " \
		+ f"WHERE PeoplePersons.People IN ({authlist})",
		st.session_state.connection)

	authors = authors.sort_values(['People', 'Order'])
	cita = authors.groupby('People').size().reset_index()
	cita['author'] = None

	for a in cita.People:
		#print(f"{a=}")
		l = authors.loc[authors.People == a, 'LastName'].values.tolist()
		l = [m for m in l if pd.notnull(m)]
		#print(f"{l=}")
		if len(l) == 1:
			cita.loc[cita.People == a, 'author'] = l[0]
		elif len(l) == 2:
			cita.loc[cita.People == a, 'author'] = l[0] + ' & ' + l[1]
		elif len(l) > 2:
			acc = ', '.join(l[:-1]) + ' & ' + l[-1]
			cita.loc[cita.People == a, 'author'] = acc
		

	rec_table = rec_table.merge(cita, how='left', left_on='refAuthor', right_on='People')

	def get_citation(row):
		out = None
		if row.refYear and row.author and row.refName:
			out = f"{row.author}. {int(row.refYear)}. {row.refName}"
		return out

	rec_table['bibliographicCitation'] = rec_table.apply(get_citation, axis=1) 

	return rec_table


def validate_search():
	
	#TODO Implement a routine to select the latest geocoding per occurrence. Currently only Geocodings from Geocoder=1 (Maps_2020) are queried.
	
	querybits = (
		"SELECT",
		"OccurrenceID, SpecimenID, GeocodingID,",
		"Specimens.SpecimenCode AS 'catalogNumber', Occurrences.Type AS 'basisOfRecord', Institutions.Code AS 'institutionCode', Sources.Author AS 'refAuthor', Sources.Name AS 'refName', Sources.Year AS 'refYear', Occurrences.CollectorVerbatim AS 'recordedBy', Occurrences.CollectionNumberVerbatim AS 'recordNumber', Occurrences.DateInit AS 'eventDate', Taxa.Name AS 'scientificName', Taxa.Author AS 'scientificNameAuthorship', Identifications.IdentifiedByVerbatim AS 'identifiedBy', Identifications.Date AS 'dateIdentified', Locations.Country AS 'country', Locations.Admin01 AS 'stateProvince', Locations.Admin02 AS 'municipality', Locations.Admin03 as 'county', Locations.Name AS 'localityVerbatim', Locations.ElevationMin AS 'minimumElevationInMeters', Locations.ElevationMax AS 'maximumElevationInMeters', Geocodings.InterpretedLat AS 'decimalLatitude', Geocodings.InterpretedLon AS 'decimalLongitude'",
		"FROM Occurrences",
		"LEFT JOIN Specimens ON Specimens.Occurrence=Occurrences.OccurrenceID",
		"LEFT JOIN Institutions ON InstitutionID=Specimens.Institution",
		"LEFT JOIN Sources ON SourceID=Occurrences.Reference",
		"LEFT JOIN Identifications ON Identifications.Occurrence=OccurrenceID",
		"LEFT JOIN Taxa ON TaxonID=Identifications.Name",
		"LEFT JOIN Locations ON LocationID=Occurrences.Location",
		"LEFT JOIN Geocodings ON LocationID=Geocodings.Location",
		"WHERE Geocoder = 1 AND "
	)

	query = " ".join(querybits)
	criteria = []

	if len(st.session_state.colectores) > 0:

		# Not a simple and readable solution, but elegantly avoids keeping a second 
		# list for People IDs	
		nums = reduce(
			lambda x,y : x+y, 
			map(
				lambda x: re.findall(r"\(ID: (\d+)\)", x), 
				st.session_state.colectores
			)
		)

		collstr = ", ".join(nums)
		criteria.append(f"Collector IN ({collstr})")

	if len(st.session_state.taxon) > 0:
		nums = []

		taxids = reduce(
			lambda x,y : x+y, 
			map(
				lambda x: re.findall(r"\(ID: (\d+)\)", x), 
				st.session_state.taxon
			)
		)

		for ti in taxids:
			nums += get_children_taxa(int(ti))
		
		taxstr = ", ".join(set([str(i) for i in nums]))
		criteria.append(f"Identifications.Name IN ({taxstr})")

	if st.session_state.no_coleccion:

		if re.search(r"\-", st.session_state.no_coleccion):
			bits = re.split(r"\-", st.session_state.no_coleccion)
			criteria.append(f"CollectionNumber >= {bits[0]} AND CollectionNumber <= {bits[1]}")

		else:
			criteria.append(f"CollectionNumber = {st.session_state.no_coleccion}")

	if st.session_state.fecha_0: 
		
		if st.session_state.fecha_f:
			criteria.append(f"DateInit >= '{st.session_state.fecha_0}' AND DateEnd <= '{st.session_state.fecha_f}'")
		else:
			criteria.append(f"DateInit = '{st.session_state.fecha_0}'")

	query += " AND ".join(criteria)
	recs = pd.read_sql(query, st.session_state.connection)
	recs = set_taxonomic_fields(recs)
	recs = literature_fields(recs)
	#error_window(f"{recs.shape=}")
	recs = recs[[
		#"OccurrenceID", "SpecimenID", "GeocodingID",
		'catalogNumber', 'basisOfRecord', 'institutionCode',
		'bibliographicCitation',
		'recordedBy', 'recordNumber', 'eventDate', 
		'taxonRank', 'scientificName', 'scientificNameAuthorship', 
		'family', 'genus', 'specificEpithet', 'infraspecificEpithet',
		'identifiedBy', 'dateIdentified', 
		'country', 'stateProvince', 'municipality', 'county', 'localityVerbatim',
		'decimalLatitude', 'decimalLongitude', 
		'minimumElevationInMeters', 'maximumElevationInMeters'
		
	]]
	st.session_state.dwc = recs.to_csv(index=False)
	st.session_state.download = True


def get_children_taxa(taxid):

	qu = f"SELECT DISTINCT TaxonID FROM Taxa WHERE Parent = {taxid}"
	thchildren = pd.read_sql_query(qu, st.session_state.connection)
	
	if thchildren.shape[0] > 0:
		acc = []
	
		for thid in thchildren.TaxonID:
			acc += get_children_taxa(thid)
	
		return acc
	
	else:
		return [taxid]
	

def buscar_taxon():
#	target_ids = []
	qu = f"SELECT DISTINCT TaxonID, Name FROM Taxa WHERE Name REGEXP '{st.session_state.taxon_pre}'"	
	sugg1 = pd.read_sql_query(qu, st.session_state.connection)
	sugg1["taxa"] = sugg1.Name.apply(str) + " (ID: " + sugg1.TaxonID.apply(str) + ")"
	st.session_state.taxon_posible = sugg1.taxa.tolist()


def buscar_colector():

	sugg = pd.read_sql_query(
		f"SELECT DISTINCT LastName, FirstName, People FROM Occurrences LEFT JOIN PeoplePersons ON Occurrences.Collector=PeoplePersons.People LEFT JOIN Persons ON PersonID=Person WHERE LastName REGEXP '{st.session_state.colector_pre}'",
		st.session_state.connection
	)

	sugg["name"] = sugg.LastName.apply(str) + ", " + sugg.FirstName.apply(str) + " (ID: " +  sugg.People.apply(str) + ")"

	st.session_state.colector_posible = sugg.name.tolist()


def process_collectors():

	if "recordedBy" in st.session_state.indata.columns:

		indb = pd.read_sql_query(
			f"SELECT DISTINCT NameVerbatim FROM Persons",
			st.session_state.connection
		)
		indb["NameVerbatimAlt"] = indb.NameVerbatim.str.replace(
			r"[\.,]", "", regex=True
		)
		indb["NameVerbatimAlt"] = indb.NameVerbatimAlt.str.replace(
			r"\s+", "", regex=True
		)
		indb["NameVerbatimAlt"] = indb.NameVerbatimAlt.str.lower()
		indb["NameVerbatimAlt"] = indb.NameVerbatimAlt.apply(unidecode)

		st.session_state.indata["recordedBy"
			] = st.session_state.indata.recordedBy.str.replace(r"\s+", " ", regex=True)
		st.session_state.indata["recordedBy"
			] = st.session_state.indata.recordedBy.str.replace(r"\.\s+", ".", regex=True)
		st.session_state.indata["recordedBy"
			] = st.session_state.indata.recordedBy.str.replace(r"^\s+", "", regex=True)
		st.session_state.indata["recordedBy"
			] = st.session_state.indata.recordedBy.str.replace(r"\s+$", "", regex=True)

		st.session_state.coll_map = {
				i:{
					"recordedByAlt": None, 
					"candidates": None, 
					} for i in sorted(set(st.session_state.indata.recordedBy.tolist()))
			}
		
		for thcoll in st.session_state.coll_map:

			st.session_state[f"coll_sel_{thcoll}"] = None
			st.session_state.coll_map[thcoll]["recordedByAlt"] = re.sub(r"[\.,]", "", thcoll)
			st.session_state.coll_map[thcoll]["recordedByAlt"] = re.sub(
				r"\s+", "", st.session_state.coll_map[thcoll]["recordedByAlt"])
			st.session_state.coll_map[thcoll]["recordedByAlt"
				] = st.session_state.coll_map[thcoll]["recordedByAlt"].lower()
			st.session_state.coll_map[thcoll]["recordedByAlt"
				] = unidecode(st.session_state.coll_map[thcoll]["recordedByAlt"])
			res = process.extract(
				st.session_state.coll_map[thcoll]["recordedByAlt"], 
				indb.NameVerbatimAlt.tolist(), 
				scorer=distance.Levenshtein.distance, 
				limit=5
			)
			thidx = [i[2] for i in res]
			st.session_state.coll_map[thcoll]["candidates"] = [indb.NameVerbatim.tolist()[m] for m in thidx]
			st.session_state.coll_map[thcoll]["candidates"].append("Nuevo colector para ingresar")

	return None		


def update_collectors():

	lastpersonid = st.session_state.connection.execute(text("SELECT MAX(PersonID) from Persons")).scalar()
	lastpersonidori = lastpersonid
	personids = []
	lastpeopleid = st.session_state.connection.execute(text("SELECT MAX(PeopleID) from People")).scalar()
	insert_sta = "INSERT INTO Persons (PersonID, NameVerbatim) VALUES "
	insert_bits = []
	for thcoll in st.session_state.coll_map.keys():

		if st.session_state[f"coll_sel_{thcoll}"] == "Nuevo colector para ingresar":
			# Insert thcoll in db
			insert_bits.append(f"({(lastpersonid+1)},'{thcoll}')")
			lastpersonid += 1
			personids.append(lastpersonid)

		else:
			# Replace selected collector in st.session_state.indata
			st.session_state.indata.loc[
				st.session_state.indata.recordedBy == thcoll,
				"recordedBy"
			] = st.session_state[f"coll_sel_{thcoll}"]

	if len(insert_bits) > 0:
		insert_sta += ", ".join(insert_bits)
		st.session_state.connection.execute(text(insert_sta))
		st.session_state.connection.commit()

		insert_sta_bis_bis = "INSERT INTO People (PeopleID) VALUES "
		peopleids = [f"{i}" for i in range((lastpeopleid+1), (lastpeopleid+len(personids)+1))]
		insert_sta_bis_bis += ", ".join([f"({i})" for i in peopleids])	
		st.session_state.connection.execute(text(insert_sta_bis_bis))
		st.session_state.connection.commit()


		insert_sta_bis = "INSERT INTO PeoplePersons (Person, People, `Order`) VALUES "
		insert_bits_bis = []
		for r,l in zip(personids, peopleids):
			insert_bits_bis.append(f"({r}, {l}, 1)")
		insert_sta_bis += ", ".join(insert_bits_bis)
		st.session_state.connection.execute(text(insert_sta_bis))
		st.session_state.connection.commit()

		#error_window(f"{lastpersonidori=}\n\n{lastpeopleid=}\n\n{insert_sta=}\n\n{insert_sta_bis_bis=}\n\n{insert_sta_bis=}")


def execute_update():

	if st.session_state.upcsv:
		st.session_state.indata = pd.read_csv(st.session_state.upcsv)

	else:
		error_window("Error al leer el archivo csv!!!!")
	
	if isinstance(st.session_state.indata, pd.DataFrame):
		process_collectors()
		

	else:
		error_window("El archivo de entrada no pudo ser leido como una tabla. Verifique que se ajuste al formato csv estricto.")

################################################################################
###						Formato principal
################################################################################

with st.form(
	"Authentication",
	clear_on_submit=True,
	):

	st.text_input(
		label="Usuario",
		help="Usuario de la base de datos. Si no tiene usuario contacte al administrador de la DB (nelson.salinas@jbb.org.co).",
		placeholder='Usuario',
		value=None,
		key="username"
	)

	st.text_input(
		label="Password",
		help="Password de usuario. Si no tiene usuario contacte al administrador de la DB (nelson.salinas@jbb.org.co).",
		placeholder='Password',
		value=None,
		key="password",
		type="password",
	)

	st.form_submit_button('Validar', on_click=validate_user)


#####     Botón de cierre de conección

if st.session_state.connection:
	salida = st.empty()

	with salida.form("Cerrar DB"):
		st.form_submit_button('Cerrar connección', on_click=close_db)
		
		if st.session_state.connection is None:
			salida.empty()


#####     Tipo de consulta

if st.session_state.connection:
	consul = st.empty()

	with consul.form("Tipo de consulta"):
		
		st.markdown("¿Cuál es la clase de consulta que desea realizar? Todas las consultas son ejecutadas a nivel de registros.")
		
		st.selectbox(
			"Tipo de consulta", 
			[
				"Actualización múltiple",
				#"Actualización individual",
				"Búsqueda",
			],
			index=0,
			key="consulta",
			placeholder="Seleccione la clase de consulta.",
			help="Tipo de consulta que desea realizar.",

		)

		st.form_submit_button(
			'Enviar', 
			on_click=validate_consulta
		)

		if st.session_state.connection is None:
			consul.empty()

if st.session_state.consulta == "Búsqueda":
	busq = st.empty()

	with busq.form("Formato de búsqueda"):

		st.markdown("# Búsqueda\nA continuación puede digitar la información relacionada a diferentes campos para constituir una consulta a la base de datos. No es necesario utilizar todos los criterios, pero al menos uno debe ser empleado.")

		######     Formato de colectores

		st.markdown("-----\n### Colector\nSi está interesado en buscar registros colectados por alguien en particular, primero digite parte del nombre del colector en la caja de la izquierda y presione el botón `Buscar colector`. A continuación los nombres de colectores encontrados en la base de datos y similares a la consulta aparecerán en la caja de la derecha. Seleccione las opciones que se ajustan a su criterio de búsqueda.")

		b0, b1 = st.columns([1, 1])

		with b0:

			st.text_input(
				label="Colector principal",
				help="Consulta preliminar del nombre del colector.",
				placeholder="Colector",
				value=None,
				key="colector_pre"
			)

			st.form_submit_button('Buscar colector', on_click=buscar_colector)

		with b1:

			st.multiselect(
				label="Colectores sugeridos",
				help="Colectores encontrados en la base de datos con similaridad a la consulta preliminar.",
				options=st.session_state.colector_posible,
				key="colectores",
				accept_new_options=False
			)

		######     Formato de número de colección

		st.markdown("-----\n### Número de colección\n")
		
		st.text_input(
			label="Número de colección",
			help="Digite un número o un rango de números separados por un guión (por ejemplo, '123' o '200-210')",
			placeholder="Número de colección",
			value=None,
			key="no_coleccion"
		)

		st.markdown("-----\n### Fecha de colecta\n")
		
		c0, c1 = st.columns([1, 1])

		with c0:

			st.date_input(
				label="Fecha inicial de colecta",
				help="Fecha inicial de colecta. Debe ser anterior a la fecha final de colecta.",
				value=None, #yesterday_date,
				min_value=datetime.date(1400, 1, 1),
				max_value="today",
				key="fecha_0"
			)

		with c1:

			st.date_input(
				label="Fecha final de colecta",
				help="Fecha final de colecta. Debe ser igual o posterior a la fecha inicial de colecta.",
				value=None, #today_date,
				min_value=datetime.date(1400, 1, 1),
				max_value="today",
				key="fecha_f"
			)


		st.markdown("-----\n### Táxon\nSi está interesado en buscar registros de un grupo taxonómico, primero digite parte del nombre del taxón en la caja de la izquierda y presione el botón `Buscar táxon`. A continuación los nombres taxonómicos sugeridos aparecerán en la caja de la derecha. Seleccione las opciones que se ajustan a su criterio de búsqueda.")


		d0, d1 = st.columns([1, 1])

		with d0:

			st.text_input(
				label="Grupo taxonómico",
				help="Grupo taxonómico que se quiere consultar (e.g., `Asteraceae`).",
				placeholder="Taxón",
				value=None,
				key="taxon_pre"
			)

			st.form_submit_button('Buscar táxon', on_click=buscar_taxon)


		with d1:

			st.multiselect(
				label="Grupo taxonómico sugerido",
				help="Grupo(s) taxonómico(s) sugeridos presentes en la base de datos.",
				options=st.session_state.taxon_posible,
				default=None,
				key="taxon",
				accept_new_options=False
			)

		
#		st.markdown("-----\n### Ubicación espacial de las coordenadas\n")
#
#		st.text_input(
#			label="Localidad",
#			help="Localidad de Bogotá de la cual se quiere consultar registros.",
#			placeholder="Localidad",
#			value=None,
#			key="localidad"
#		)
#
#		st.text_input(
#			label="Sitio de colección",
#			help="Palabra(s) claves(s) de la ubicación geográfica donde se registraron las muestras.",
#			placeholder="Sitio",
#			value=None,
#			key="sitio"
#		)
#
#		st.file_uploader(
#			label="Polígono",
#			help="Shapefile delimitando un polígono de búsqueda.",
#			key="shape",
#			type="shp",
#		)

		st.markdown("\n-----\n")

		st.form_submit_button(
			'Buscar', 
			on_click=validate_search
		)

	if st.session_state.download:

		# The following line display the table, intended only for debbuging
		#st.dataframe(pd.read_csv(StringIO(st.session_state.dwc)))

		st.download_button(
			"Descarga DwC",
			data=st.session_state.dwc,
			file_name="consulta_DwC_Mutis.csv",
			mime="text/csv",
		)			

elif st.session_state.consulta == "Actualización múltiple":
	mult = st.empty()

	with mult.form("Formato de actualización múltiple"):

		st.markdown("# Actualización de múltiples registros\nEn la siguiente forma puede cargar un archivo DarwinCore para actualizar o insertar varios registros en la base de datos Mutis. Tenga en cuenta que el archivo debe seguir un formato csv estricto: **_comas como separadores de campo y puntos como indicador de decimales_**. \n\nInicialmente, la aplicación verificará que si los colectores ya fueron ingresados en la base de datos, para lo cual los nombres digitados en la columna *recordedBy* deben estar homogenizados, siguiendo el formato ```apellido(s), iniciales de los nombres``` (p.e., ```García-Barriga, H.```)")

		st.file_uploader(
			"Seleccione un archivo", 
			type='csv',
			accept_multiple_files = False,
			key='upcsv',
			help = "El archivo DarwinCore debe tener formato csv estricto",
			#on_change=process_infile,
		)

		st.form_submit_button(
			"Procesar colectores",
			on_click=execute_update,
		)

		if isinstance(st.session_state.indata, pd.DataFrame) and \
			isinstance(st.session_state.coll_map, dict) and \
			len(st.session_state.coll_map) > 0:

			for thcoll in st.session_state.coll_map.keys():
				
				st.write("-----")
				st.write(f"Colector original: {thcoll}\n\nColectores propuestos:")				
				st.selectbox(
					"Colectores en Mutis",
					st.session_state.coll_map[thcoll]["candidates"],
					index=0,
					placeholder="Seleccione el colector apropiado",
					key=f"coll_sel_{thcoll}",
					#key=st.session_state.coll_selections[thcoll]
				)

			st.form_submit_button(
				"Enviar selección de colectores",
				on_click=update_collectors
			)

exit()



