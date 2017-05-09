from functools import lru_cache
import os.path

from cached_property import cached_property
import requests


class PipeChild:
    def __init__(self, pipe, identifier, data):
        self.pipe = pipe
        self.identifier = identifier
        self.data = data
        self.client = pipe.client

    def __str__(self):
        return '<{} #{}: {}>'.format(self.__class__.__name__, self.identifier, self.data)

    def __repr__(self):
        return self.__str__()


class Card(PipeChild):
    pass


class Phase(PipeChild):
    @property
    def fields(self):
        return self.data['fields']

    @cached_property
    def cards(self):
        cards = []
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

        self._field_cache = {}

    def create_card(self, card_title, values):
        field_values = []
        for key, value in values.items():
            field_id = self.get_field(key)
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

    def get_field(self, key):
        if key in self._field_cache:
            return self._field_cache[key]

        for phase in self.phases:
            for field_data in phase.data['fields']:
                self._field_cache[field_data['label']] = field_data['id']

                if field_data['label'] == key:
                    return self._field_cache[key]

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

    @cached_property
    def headers(self):
        return {
            "X-User-Email": self.email,
            "X-User-Token": self.token,
        }

    def get_url(self, endpoint):
        url = os.path.join(self.base_url, endpoint.lstrip('/'))
        return url

    def get(self, endpoint):
        print('get', endpoint)
        response = requests.get(self.get_url(endpoint), headers=self.headers)
        try:
            response.raise_for_status()
        except:
            print(response.text)
            raise

        return response

    def post(self, endpoint, data):
        print('post', endpoint)
        response = requests.post(self.get_url(endpoint), json=data, headers=self.headers)
        try:
            response.raise_for_status()
        except:
            print(response.text)
            raise

        return response

    def get_pipe(self, pipe_id):
        url = '/pipes/{pipe_id}.json'.format(pipe_id=pipe_id)
        pipe_data = self.get(url)
        return Pipe(self, pipe_id, pipe_data.json())
