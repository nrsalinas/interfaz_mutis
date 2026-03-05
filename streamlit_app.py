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
#TODO
#TODO 
#TODO 
#TODO###########################################################################

import re
from functools import reduce
import datetime
import pytz
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine

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
if not "taxon_sug" in st.session_state: st.session_state.taxon_sug = []


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


def validate_search():
	query = "SELECT * "

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
		query += f"FROM Occurrences WHERE Collector IN ({collstr}) "

		error_window(query)

def buscar_colector():

	sugg = pd.read_sql_query(
		f"SELECT DISTINCT LastName, FirstName, People FROM Occurrences LEFT JOIN PeoplePersons ON Occurrences.Collector=PeoplePersons.People LEFT JOIN Persons ON PersonID=Person WHERE LastName REGEXP '{st.session_state.colector_pre}'",
		st.session_state.connection
	)

	sugg["name"] = sugg.LastName.apply(str) + ", " + sugg.FirstName.apply(str) + " (ID: " +  sugg.People.apply(str) + ")"

	st.session_state.colector_posible = sugg.name.tolist()


def buscar_taxon():

	sugg = pd.read_sql_query(
		f"SELECT Name FROM Taxa WHERE Name REGEXP '{st.session_state.taxon_pre}'",
		st.session_state.connection
	)

	st.session_state.taxon_sug = sugg.Name.tolist()


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
				#"Actualización",
				#"Inserción", 
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
				help="Fecha final de colecta. Debe ser posterior a la fecha inicial de colecta.",
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
				options=st.session_state.taxon_sug,
				default=None,
				key="taxon",
				accept_new_options=False
			)


		st.markdown("-----\n### Ubicación espacial de las coordenadas\n")

		st.text_input(
			label="Localidad",
			help="Localidad de Bogotá de la cual se quiere consultar registros.",
			placeholder="Localidad",
			value=None,
			key="localidad"
		)

		st.text_input(
			label="Sitio de colección",
			help="Palabra(s) claves(s) de la ubicación geográfica donde se registraron las muestras.",
			placeholder="Sitio",
			value=None,
			key="sitio"
		)

		st.file_uploader(
			label="Polígono",
			help="Shapefile delimitando un polígono de búsqueda.",
			key="shape",
			type="shp",
		)

		st.form_submit_button(
			'Buscar', 
			on_click=validate_search
		)

		if st.session_state.query:
			st.markdown(st.session_state.query)
exit()



