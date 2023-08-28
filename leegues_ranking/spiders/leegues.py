import scrapy
import pprint
# response.xpath('//div[starts-with(@id, "heading_insc_cat_")]/..')
# wells[0].xpath('.//a[contains(@class, "panel-title")]/text()').get().strip()

class LeeguesSpider(scrapy.Spider):
    name = "leegues"
    allowed_domains = ["app.leegues.com"]
    start_urls = ["https://app.leegues.com/Torneios/4392/liga-getsemani-etapa-de-junho-de-2023"]

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url=f'{url}/Inscritos', callback=self.parse, meta={'dont_obey_robotstxt': True})

    def follow_category_dropdown(self, response, category_id):
        href = response.xpath(f'//ul[contains(@class, "dropdown-menu-chaves")]//li//a[contains(@href, "Categorias/{category_id}/")]/@href').get()
        if not href:
            return
        yield response.follow(href, callback=self.parse_draws, cb_kwargs=dict(category_id=category_id))

    def parse_subscriptions(self, response):
        wells = response.xpath('//div[starts-with(@id, "heading_insc_cat_")]/..')
        categories = []
        for well in wells:
            category_name = well.xpath('.//a[contains(@class, "panel-title")]/text()').get().strip().lower()
            category_id = well.xpath('.//div[starts-with(@id, "heading_insc_cat_")]//@id').get().strip().replace('heading_insc_cat_', '')
            categories.append(category_id)
            yield {'category': {'id': category_id, 'name': category_name}}

            players = well.xpath('.//a[contains(@class, "player-divider")]')
            for player in players:
                player_href = player.xpath('./@href').get()
                player_name = ''.join(player.xpath('.//text()').getall()).strip()
                yield {'player': {'href': player_href, 'name': player_name}}

        for category_id in categories:
            yield from self.follow_category_dropdown(response, category_id)

    def extract_from_group_table(self, group_table):
        rows = group_table.xpath('.//tbody//tr[@data-jogador]')
        ranked_players = {}

        for row in rows:
            player_href = row.css('a.player-divider').xpath('./@href').get()
            wins = int(row.xpath('./td[3]/text()').get())
            games = int(row.xpath('./td[4]/text()').get())
            points = int(row.xpath('./td[5]/text()').get())
            ranked_players[player_href] = (-1, wins, games, points)
        return ranked_players
    
    def extract_from_brackets(self, brackets):
        phases = brackets.xpath('./tbody/tr/td')

        player_to_wins = {}

        for i, phase in enumerate(phases):
            games_from_phase = phase.css('table.table-jogo')
            for game in games_from_phase:
                players = game.css('a.player-divider').xpath('./@href').getall()
                winner = game.css('tr.linha-vencedor a.player-divider').xpath('./@href').get()
                for player in players:
                    player_to_wins[player] = i
                    if player == winner:
                        player_to_wins[player] += 1
        
        return {
            player: (phase, 0, 0, 0)
            for player, phase in player_to_wins.items()
        }
    

    def generate_ranking(self, ranked_players):
        def count_greater(x):
            return sum(ranked_player > x for ranked_player in ranked_players.values())
        
        return {
            ranked_player: count_greater(v)
            for ranked_player, v in ranked_players.items()
        }


    def parse_draws(self, response, category_id):
        group_tables = response.xpath('//div[contains(@id, "grupos_")]').css('div.tab-table')

        ranked_players = {}
        for group_table in group_tables:
            ranked_players.update(self.extract_from_group_table(group_table))

        brackets = response.css('table.chave-geral')
        ranked_players.update(self.extract_from_brackets(brackets))
        
        yield {
            "result": {
                "category": category_id,
                "ranking": self.generate_ranking(ranked_players),
            }
        }

    def parse(self, response):
        yield from self.parse_subscriptions(response)
