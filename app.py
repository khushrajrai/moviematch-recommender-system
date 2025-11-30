from flask import Flask, request, jsonify, render_template
import pickle
import requests

from dotenv import load_dotenv
poster_cache = {}
load_dotenv()
import os
OMDB_API_KEY = os.getenv("OMDB_API_KEY")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

similarity_path = os.path.join(BASE_DIR, "models", "similarity_score.pkl")
pivot_path = os.path.join(BASE_DIR, "models", "final_pivot_table.pkl")

with open(similarity_path, "rb") as f:
    similarity_score = pickle.load(f)

with open(pivot_path, "rb") as f:
    final_pivot_table = pickle.load(f)


final_popular_df = pickle.load(open('models/final_popular_df.pkl','rb'))
# final_pivot_table = pickle.load(open('models/final_pivot_table.pkl','rb'))
updated_movie_df = pickle.load(open('models/updated_movie_df.pkl','rb'))
# similarity_score = pickle.load(open('models/similarity_score.pkl','rb'))

app = Flask(__name__)


def fix_imdb_id(x):
    """Ensures imdbId is in full format: tt0123456"""
    x = str(x).strip()
    # extract digits then zero-pad to 7 digits
    digits = ''.join(ch for ch in x if ch.isdigit())
    if digits == "":
        return ""
    return "tt" + digits.zfill(7)


def fetch_poster_imdb(imdb_id):
    """Server-side OMDB call to get poster URL. Returns None if not available."""
    if not imdb_id:
        return None
    # IN-MEMORY CACHE CHECK
    if imdb_id in poster_cache:
        return poster_cache[imdb_id]
    try:
        url = f"https://www.omdbapi.com/?i={imdb_id}&apikey={OMDB_API_KEY}"
        resp = requests.get(url, timeout=6)
        if resp.status_code != 200:
            poster_cache[imdb_id] = None
            return None
        data = resp.json()
        if data.get("Response") == "True":
            poster = data.get("Poster")
            if poster and poster != "N/A":
                poster_cache[imdb_id] = poster
                return poster
    except Exception as e:
        app.logger.debug("OMDB fetch error %s -> %s", imdb_id, e)
        poster_cache[imdb_id] = None
    return None

@app.route('/about')
def about():
    return render_template('about.html')



@app.route('/')
def home():
    # imdb ids and limit to top 50
    raw_ids = list(final_popular_df['imdbId'].values)[:50]
    imdb_ids = [fix_imdb_id(i) for i in raw_ids]

    titles = list(final_popular_df['title'].values)[:50]
    votes = list(final_popular_df['num_ratings'].values)[:50]
    rating = list(final_popular_df['avg_ratings'].values)[:50]

    # Fetch posters server-side and build list same length as titles
    posters = []
    for imdb in imdb_ids:
        poster = fetch_poster_imdb(imdb)
        posters.append(poster)  # None if missing

    return render_template(
        'index.html',
        api_key=OMDB_API_KEY,
        title=titles,
        imdbId=imdb_ids,
        votes=votes,
        rating=rating,
        posters=posters
    )


@app.route('/recommendation')
def recommend_ui():
    titles = list(updated_movie_df["title"].values)
    return render_template('recommendation.html', titles=titles)


@app.route('/recommend_books', methods=['POST'])
def recommend():
    movie_name = request.form.get('movie_name')

    if movie_name not in final_pivot_table.index:
        return render_template(
            'recommendation.html',
            error="Movie not found! Please enter a valid movie name.",
            titles=list(updated_movie_df["title"].values),
            api_key=OMDB_API_KEY
        )

    index = final_pivot_table.index.get_loc(movie_name)

    similar_items = sorted(
        list(enumerate(similarity_score[index])),
        key=lambda x: x[1],
        reverse=True
    )[1:9]

    data = []
    for i in similar_items:
        temp_df = updated_movie_df[
            updated_movie_df["title"] == final_pivot_table.index[i[0]]
        ].drop_duplicates("title")

        imdb_fixed = fix_imdb_id(temp_df["imdbId"].values[0])
        poster_url = fetch_poster_imdb(imdb_fixed)

        data.append({
        "imdbId": imdb_fixed,
        "title": temp_df["title"].values[0],
        "poster": poster_url
        })

    return render_template(
        "recommendation.html",
        results=data,
        titles=list(updated_movie_df["title"].values),
        api_key=OMDB_API_KEY
    )


if __name__ == "__main__":
    
    app.run(debug=True)




