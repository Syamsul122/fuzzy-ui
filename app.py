from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
# Konfigurasi CORS: Opsi 2 (Direkomendasikan untuk Produksi)
# Menggunakan Environment Variable 'ALLOWED_ORIGINS'
ALLOWED_ORIGINS_STR = os.environ.get("ALLOWED_ORIGINS", "").split(',')
ALLOWED_ORIGINS = [origin.strip() for origin in ALLOWED_ORIGINS_STR if origin.strip()]

CORS(app, resources={r"/*": {"origins": ALLOWED_ORIGINS, "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"], "allow_headers": ["Content-Type"]}})
# Menggunakan r"/*" agar semua rute (termasuk /fuzzy dan /reset) tercakup.
# Menambahkan "OPTIONS" untuk preflight requests.

# Hitung nilai pakar
def hitung_pakar(tulis, keterampilan, wawancara, kesehatan):
    a = (tulis + keterampilan) / 2
    b = (wawancara + kesehatan + a) / 3
    return b

# Fungsi keanggotaan fuzzy linear
def fuzzy_linear(x, x1, x2, naik=True):
    if naik:
        if x <= x1:
            return 0.0
        elif x >= x2:
            return 1.0
        else:
            return (x - x1) / (x2 - x1)
    else:
        if x <= x1:
            return 1.0
        elif x >= x2:
            return 0.0
        else:
            return (x2 - x) / (x2 - x1)

# Fuzzyfikasi input
def fuzzify_inputs(tulis, keterampilan, wawancara, kesehatan):
    return {
        'tulis': {
            'lulus': fuzzy_linear(tulis, 25, 75, naik=True),
            'tidak_lulus': fuzzy_linear(tulis, 25, 75, naik=False)
        },
        'keterampilan': {
            'lulus': fuzzy_linear(keterampilan, 25, 75, naik=True),
            'tidak_lulus': fuzzy_linear(keterampilan, 25, 75, naik=False)
        },
        'wawancara': {
            'lulus': fuzzy_linear(wawancara, 55, 75, naik=True),
            'tidak_lulus': fuzzy_linear(wawancara, 55, 75, naik=False)
        },
        'kesehatan': {
            'lulus': fuzzy_linear(kesehatan, 50, 70, naik=True),
            'tidak_lulus': fuzzy_linear(kesehatan, 50, 70, naik=False)
        }
    }


# Defuzzifikasi Tsukamoto
def hitung_z(predikat, alpha):
    if predikat == 'diterima':
        return alpha * 50 + 25
    else:
        return 75 - alpha * 50

# Aturan fuzzy (16 kombinasi)
rule_output_map = {
    ('lulus', 'lulus', 'lulus', 'lulus'): 'diterima',
    ('lulus', 'lulus', 'lulus', 'tidak_lulus'): 'tidak_diterima',
    ('lulus', 'lulus', 'tidak_lulus', 'lulus'): 'tidak_diterima',
    ('lulus', 'lulus', 'tidak_lulus', 'tidak_lulus'): 'tidak_diterima',
    ('lulus', 'tidak_lulus', 'lulus', 'lulus'): 'diterima',
    ('lulus', 'tidak_lulus', 'lulus', 'tidak_lulus'): 'tidak_diterima',
    ('lulus', 'tidak_lulus', 'tidak_lulus', 'lulus'): 'tidak_diterima',
    ('lulus', 'tidak_lulus', 'tidak_lulus', 'tidak_lulus'): 'tidak_diterima',
    ('tidak_lulus', 'lulus', 'lulus', 'lulus'): 'diterima',
    ('tidak_lulus', 'lulus', 'lulus', 'tidak_lulus'): 'tidak_diterima',
    ('tidak_lulus', 'lulus', 'tidak_lulus', 'lulus'): 'tidak_diterima',
    ('tidak_lulus', 'lulus', 'tidak_lulus', 'tidak_lulus'): 'tidak_diterima',
    ('tidak_lulus', 'tidak_lulus', 'lulus', 'lulus'): 'diterima',
    ('tidak_lulus', 'tidak_lulus', 'lulus', 'tidak_lulus'): 'tidak_diterima',
    ('tidak_lulus', 'tidak_lulus', 'tidak_lulus', 'lulus'): 'tidak_diterima',
    ('tidak_lulus', 'tidak_lulus', 'tidak_lulus', 'tidak_lulus'): 'tidak_diterima'
}

# Fuzzy Tsukamoto
def fuzzy_tsukamoto(tulis, keterampilan, wawancara, kesehatan):
    fuzzy_vals = fuzzify_inputs(tulis, keterampilan, wawancara, kesehatan)
    rules = []
    rule_no = 1

    for t in ['lulus', 'tidak_lulus']:
        for k in ['lulus', 'tidak_lulus']:
            for w in ['lulus', 'tidak_lulus']:
                for h in ['lulus', 'tidak_lulus']:
                    alpha = round(min(
                        fuzzy_vals['tulis'][t],
                        fuzzy_vals['keterampilan'][k],
                        fuzzy_vals['wawancara'][w],
                        fuzzy_vals['kesehatan'][h]
                    ), 2)
                    status_key = (t, k, w, h)
                    predikat = rule_output_map.get(status_key, 'tidak_diterima')
                    z = hitung_z(predikat, alpha)
                    z = int(-(-z // 1))  # Pembulatan ke atas (ceil)
                    alpha_z = round(alpha * z, 2)
                    rules.append({
                        'rule': rule_no,
                        'status': [t, k, w, h],
                        'predikat': predikat,
                        'alpha': alpha,
                        'z': z,
                        'alpha_z': alpha_z
                    })
                    rule_no += 1

    total_alpha_z = int(round(sum(r['alpha_z'] for r in rules)))
    total_alpha = round(sum(r['alpha'] for r in rules), 2)
    hasil_akhir = total_alpha_z / total_alpha if total_alpha != 0 else 0
    status_akhir = 'DITERIMA' if hasil_akhir >= 70 else 'TIDAK DITERIMA'

    return hasil_akhir, status_akhir, rules

@app.route('/fuzzy-detail', methods=['POST'])
def fuzzy_detail():
    data = request.json
    tulis = data.get('tulis')
    keterampilan = data.get('keterampilan')
    wawancara = data.get('wawancara')
    kesehatan = data.get('kesehatan')

    if None in [tulis, keterampilan, wawancara, kesehatan]:
        return jsonify({'error': 'Input tidak lengkap'}), 400

    hasil_akhir, status_akhir, rules = fuzzy_tsukamoto(tulis, keterampilan, wawancara, kesehatan)
    return jsonify({
        'hasil_akhir': hasil_akhir,
        'status_akhir': status_akhir,
        'rules': rules
    })


# Fungsi menghitung average rank (jika nilai sama dihitung rata-rata)
def average_rank(values, descending=True):
    indexed_values = list(enumerate(values))
    indexed_values.sort(key=lambda x: -x[1] if descending else x[1])
    ranks = [0] * len(values)
    i = 0
    while i < len(indexed_values):
        same_value_group = [indexed_values[i]]
        j = i + 1
        while j < len(indexed_values) and round(indexed_values[j][1], 2) == round(indexed_values[i][1], 2):
            same_value_group.append(indexed_values[j])
            j += 1
        avg_rank = sum(range(i + 1, j + 1)) / len(same_value_group)
        for idx, _ in same_value_group:
            ranks[idx] = avg_rank
        i = j
    return ranks

data_peserta = []

@app.route('/fuzzy', methods=['POST'])
def hitung_fuzzy():
    global data_peserta
    data = request.json

    if isinstance(data, dict):
        nama = data.get('nama', f'Peserta-{len(data_peserta)+1}')
        tulis = data.get('tulis')
        keterampilan = data.get('keterampilan')
        wawancara = data.get('wawancara')
        kesehatan = data.get('kesehatan')

        if None in [tulis, keterampilan, wawancara, kesehatan]:
            return jsonify({'error': 'Input tidak lengkap'}), 400

        data_peserta.append({
            'nama': nama,
            'tulis': tulis,
            'keterampilan': keterampilan,
            'wawancara': wawancara,
            'kesehatan': kesehatan
        })

    hasil = []
    for item in data_peserta:
        nama = item['nama']
        tulis = item['tulis']
        keterampilan = item['keterampilan']
        wawancara = item['wawancara']
        kesehatan = item['kesehatan']

        fuzzy_nilai, status, _ = fuzzy_tsukamoto(tulis, keterampilan, wawancara, kesehatan)
        pakar_nilai = hitung_pakar(tulis, keterampilan, wawancara, kesehatan)

        hasil.append({
            'nama': nama,
            'pakar': pakar_nilai,
            'sistem': fuzzy_nilai,
            'status': status
        })

    pakar_list = [int(round(item['pakar'])) for item in hasil]
    sistem_list = [int(round(item['sistem'])) for item in hasil]



    rank_pakar = average_rank(pakar_list, descending=True)
    rank_sistem = average_rank(sistem_list, descending=True)

    for i, item in enumerate(hasil):
        item['pakar'] = int(round(item['pakar']))
        item['sistem'] = int(round(item['sistem']))
        item['rank_pakar'] = rank_pakar[i]
        item['rank_sistem'] = rank_sistem[i]
        item['di'] = item['rank_pakar'] - item['rank_sistem']
        item['di2'] = item['di'] ** 2


    n = len(hasil)
    total_di2 = round(sum(item['di2'] for item in hasil), 2)
    spearman_rho = round(1 - (6 * total_di2) / (n * (n**2 - 1)), 3) if n > 1 else 1

    return jsonify({
        'hasil': hasil,
        'total_di2': total_di2,
        'spearman_rho': spearman_rho
    })


@app.route('/reset', methods=['POST'])
def reset_data():
    global data_peserta
    data_peserta = []
    return jsonify({"status": "reset berhasil"})

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal Server Error", "message": str(error)}), 500



