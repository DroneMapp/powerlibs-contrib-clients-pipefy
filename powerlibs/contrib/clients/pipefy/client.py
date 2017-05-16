from functools import lru_cache
import logging
import os.path

from cached_property import cached_property
import requests


class PipeChild:
    def __init__(self, pipe, identifier, data):
        self.pipe = pipe
        self.identifier = identifier
        self.data = data
        self.client = pipe.client
        self.logger = logging.getLogger(self.__class__.__name__)

    def __str__(self):
        return '<{} #{}: {}>'.format(self.__class__.__name__, self.identifier, self.data)

    def __repr__(self):
        return self.__str__()


class Card(PipeChild):
    @cached_property
    def values(self):
        the_values = {}

        for phase_details in self.data['other_phase_details']:
            for field_value in phase_details['field_values']:
                label = self.pipe.get_field_label_by_id(field_value['field_id'])
                the_values[label] = field_value['value']

        for field_value in self.data['current_phase_detail']['field_values']:
            label = self.pipe.get_field_label_by_id(field_value['id'])
            the_values[label] = field_value['value']

        return the_values


class Phase(PipeChild):
    @property
    def fields(self):
        return self.data['fields']

    @cached_property
    def cards(self):
        cards = []

        if 'cards' not in self.data:
            response = self.client.get('/phases/{}/cards.json'.format(self.data['id']))
            self.data['cards'] = response.json()

        for card_data in self.data['cards']:
            card_id = card_data['id']
            response = self.client.get('/cards/{}'.format(card_id))
            cards.append(Card(self.pipe, card_id, response.json()))

        return cards


class Pipe:
    def __init__(self, client, id, data):
        self.client = client
        self.id = id
        self.data = data
        self.logger = logging.getLogger(self.__class__.__name__)

        self._field_cache = {}

    def create_card(self, card_title, values):
        field_values = []
        for key, value in values.items():
            field_id = self.get_field_id_by_label(key)
            field_values.append({
                'field_id': field_id,
                'value': value
            })

        payload = {
            'card': {
                "title": card_title,
                "field_values": field_values,
            }
        }

        url = '/pipes/{pipe.id}/create_card.json'.format(pipe=self)
        response = self.client.post(url, payload)
        response_data = response.json()
        return Card(self, response_data['id'], response_data)

    def get_field_id_by_label(self, label):
        if label in self._field_cache:
            return self._field_cache[label]

        for phase in self.phases:
            for field_data in phase.data['fields']:
                self._field_cache[field_data['label']] = field_data['id']
                self._field_cache[field_data['id']] = field_data['label']

                if field_data['label'] == label:
                    return self._field_cache[label]

    def get_field_label_by_id(self, id):
        if id in self._field_cache:
            return self._field_cache[id]

        for phase in self.phases:
            for field_data in phase.data['fields']:
                self._field_cache[field_data['label']] = field_data['id']
                self._field_cache[field_data['id']] = field_data['label']

                if field_data['id'] == id:
                    return self._field_cache[id]

    @cached_property
    def phases(self):
        return [self.get_phase(x['id']) for x in self.data['phases']]

    @lru_cache(128)
    def get_phase(self, phase_id):
        url = '/phases/{phase_id}.json'.format(phase_id=phase_id)
        response = self.client.get(url)
        return Phase(self, phase_id, response.json())

    @cached_property
    def cards(self):
        cards = []
        for phase in self.phases:
            for card in phase.cards:
                cards.append(card)

        return cards

    def __str__(self):
        return '<Pipe {}: {}>'.format(self.id, self.data)


class PipefyClient:
    def __init__(self, email, token, base_url):
        self.token = token
        self.email = email
        self.base_url = base_url
        self.logger = logging.getLogger(self.__class__.__name__)

    @cached_property
    def headers(self):
        return {
            "X-User-Email": self.email,
            "X-User-Token": self.token,
        }

    def get_url(self, endpoint):
        url = os.path.join(self.base_url, endpoint.lstrip('/'))
        return url

    def http_request(self, method, endpoint, **kwargs):
        response = method(self.get_url(endpoint), headers=self.headers, **kwargs)
        try:
            response.raise_for_status()
        except:
            self.logger.debug(response.text)
            raise

        return response

    def get(self, endpoint):
        return self.http_request(requests.get, endpoint)

    def post(self, endpoint, data):
        return self.http_request(requests.post, endpoint, json=data)

    def patch(self, endpoint, data):
        return self.http_request(requests.patch, endpoint, json=data)

    def put(self, endpoint, data):
        return self.http_request(requests.put, endpoint, json=data)

    def delete(self, endpoint):
        return self.http_request(requests.delete, endpoint)

    def get_pipe(self, pipe_id):
        url = '/pipes/{pipe_id}.json'.format(pipe_id=pipe_id)
        pipe_data = self.get(url)
        return Pipe(self, pipe_id, pipe_data.json())
