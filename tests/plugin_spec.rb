# frozen_string_literal: true

# Run with: trmnlp test (or trmnlp test --report report)
RSpec.describe 'OSRS Collection Log' do
  let(:player_clog_payload) do
    {
      data: {
        player: 'Mikael',
        player_name_with_capitalization: 'Mikael',
        game_mode: 0,
        last_checked: '2026-11-20 20:57:56',
        last_changed: '2026-11-20 20:57:56',
        total_collections_finished: 637,
        total_collections_available: 1734,
        total_collections_in_response: 12,
        ehc: 1865.15,
        total_categories_finished: 23,
        total_categories_available: 125,
        collections_hiscores_rank: 74_239,
        items: [
          { id: 7979, count: 2, date: '2024-12-31 00:00:00' },
          { id: 4151, count: 3, date: '2025-12-28 05:58:51' },
          { id: 22_988, count: 1, date: '2026-07-01 17:55:08' },
          { id: 23_077, count: 2, date: '2026-07-02 18:45:53' },
          { id: 4753, count: 1, date: '2026-06-18 10:01:18' },
          { id: 4751, count: 1, date: '2026-06-18 09:39:09' },
          { id: 20_997, count: 1, date: '2026-08-10 12:00:00' },
          { id: 23_348, count: 1, date: '2026-11-11 12:36:48' },
          { id: 22_246, count: 1, date: '2026-11-11 12:36:04' },
          { id: 10_551, count: 1, date: '2026-11-10 18:09:31' },
          { id: 34_040, count: 1, date: '2026-11-16 10:32:19' },
          { id: 31_111, count: 1, date: '2026-11-20 20:57:56' }
        ]
      }
    }
  end

  let(:recent_items_payload) do
    {
      data: [
        { id: 31_111, name: 'Demon tear', date: '2026-11-20 20:57:56', date_unix: 1_795_208_276, notable_item: false },
        { id: 31_099, name: 'Mokhaiotl waystone', date: '2026-11-20 20:57:56', date_unix: 1_795_208_276, notable_item: false },
        { id: 34_040, name: 'Mr McGroot', date: '2026-11-16 10:32:19', date_unix: 1_794_825_139, notable_item: true },
        { id: 3830, name: 'Saradomin page 4', date: '2026-11-16 10:32:19', date_unix: 1_794_825_139, notable_item: false },
        { id: 30_922, name: 'Minor master scroll case', date: '2026-11-11 12:38:31', date_unix: 1_794_400_711, notable_item: false },
        { id: 23_348, name: 'Tormented ornament kit', date: '2026-11-11 12:36:48', date_unix: 1_794_400_608, notable_item: false },
        { id: 22_246, name: 'Anguish ornament kit', date: '2026-11-11 12:36:04', date_unix: 1_794_400_564, notable_item: false },
        { id: 10_551, name: 'Fighter torso', date: '2026-11-10 18:09:31', date_unix: 1_794_334_171, notable_item: false },
        { id: 7331, name: 'Blue firelighter', date: '2026-11-09 12:53:51', date_unix: 1_794_228_831, notable_item: false },
        { id: 10_284, name: 'Magic comp bow', date: '2026-11-09 12:53:51', date_unix: 1_794_228_831, notable_item: false },
        { id: 2641, name: 'Dark cavalier', date: '2026-11-09 12:53:51', date_unix: 1_794_228_831, notable_item: false },
        { id: 4151, name: 'Abyssal whip', date: '2025-12-28 05:58:51', date_unix: 1_766_901_531, notable_item: true }
      ]
    }
  end

  let(:mocks) do
    {
      'https://templeosrs.com/api/collection-log/player_collection_log.php*' => { json: player_clog_payload },
      'https://templeosrs.com/api/collection-log/player_recent_items.php*' => { json: recent_items_payload }
    }
  end

  let(:custom_fields) { { rsn: 'Mikael', only_notable: '0' } }

  it_behaves_like 'a publishable recipe'

  it 'renders the OSRS Collection Log overview with all 5 categories and rank progression' do
    screen = trmnl.render(mocks:, custom_fields:)
    expect(screen).to have_text('Collection Log: Overview for Mikael')
    expect(screen).to have_text('Account Type Main: 637/1734')
    expect(screen).to have_text('Bosses')
    expect(screen).to have_text('Raids')
    expect(screen).to have_text('Clues')
    expect(screen).to have_text('Minigames')
    expect(screen).to have_text('Other')
    expect(screen).to have_text('/339')
    expect(screen).to have_text('/611')
    expect(screen).to have_text('III: Steel')
    expect(screen).to have_text('IV: Black')
    expect(screen).to have_text('Collections Logged: 637/700')
    expect(screen).to have_text('Latest Collections')
  end

  it 'computes Dragon rank for an Ironman with 1412 slots (Iron 3 Hit)' do
    iron_clog = {
      data: player_clog_payload[:data].merge(
        player: 'Iron 3 Hit',
        player_name_with_capitalization: 'Iron 3 Hit',
        game_mode: 1,
        total_collections_finished: 1412,
        total_collections_available: 1734,
        collections_hiscores_rank: nil
      )
    }
    iron_mocks = mocks.merge(
      'https://templeosrs.com/api/collection-log/player_collection_log.php*' => { json: iron_clog }
    )
    screen = trmnl.render(mocks: iron_mocks, custom_fields: { rsn: 'iron 3 hit', only_notable: '0' })
    expect(screen).to have_text('Collection Log: Overview for Iron 3 Hit')
    expect(screen).to have_text('VIII: Dragon')
    expect(screen).to have_text('IX: Gilded')
    expect(screen).to have_text('Account Type Ironman: 1412/1734')
  end

  it 'shows a clean error state when a player has no synced log' do
    err_mocks = mocks.merge(
      'https://templeosrs.com/api/collection-log/player_collection_log.php*' => {
        json: { error: { Code: 402, Message: 'Player has not synced collection log.' } }
      }
    )
    screen = trmnl.render(mocks: err_mocks, custom_fields: { rsn: 'UnsyncedUser', only_notable: '0' })
    expect(screen).to have_text('Collection Log Unavailable')
    expect(screen).to have_text('Player has not synced collection log.')
  end
end
